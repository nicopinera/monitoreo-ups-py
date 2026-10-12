import logging
import sys
import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import config.configuracion as c
from config.entorno import AjustesSNMP, Entorno, ErrorConfiguracion, cargar_entorno
from drivers.dc_ups import DataCenterUPS
from drivers.hum_ups import HumedadUPS
from drivers.state_ups import StateUPS
from infraestructura.database import RepositorioDB
from infraestructura.logger import configurar_logger
from infraestructura.notificador import Notificador
from infraestructura.snmp_client import ClienteSNMP

logger = logging.getLogger(__name__)

# Una tarea es (nombre para el log, funcion sin argumentos que devuelve las lineas de su equipo)
Tarea = tuple[str, Callable[[], list[str]]]
# Resultado de una tarea: sus lineas, o None si lanzo una excepcion
ResultadoTarea = list[str] | None


def _tarea_humedad(ajustes_snmp: AjustesSNMP) -> list[str]:
    cliente = ClienteSNMP(c.HOST_NAME_HUMEDAD, ajustes_snmp)
    return HumedadUPS(hostname=c.HOST_NAME_HUMEDAD, cliente_snmp=cliente).ejecutar(c.OID_HUMEDAD)


def _tarea_dc(ajustes_snmp: AjustesSNMP) -> list[str]:
    cliente = ClienteSNMP(c.HOST_NAME_DC, ajustes_snmp)
    return DataCenterUPS(c.HOST_NAME_DC, cliente_snmp=cliente).ejecutar(c.OID_DC)


def _tarea_state(
    host: str,
    ajustes_snmp: AjustesSNMP,
    notificador: Notificador,
    repo_db: RepositorioDB,
    fallas_para_alerta: int,
) -> list[str]:
    cliente = ClienteSNMP(host, ajustes_snmp)
    driver = StateUPS(
        hostname=host,
        cliente_snmp=cliente,
        notificador=notificador,
        rep_db=repo_db,
        fallas_para_alerta=fallas_para_alerta,
    )
    return driver.ejecutar(c.OID_UPS, c.OIDT, c.OIDTNEW)


def crear_tareas(
    ajustes_snmp: AjustesSNMP,
    notificador: Notificador,
    repo_db: RepositorioDB,
    fallas_para_alerta: int = 1,
) -> list[Tarea]:
    """
    Arma las tareas a ejecutar como una lista de (nombre, funcion).
    Cada tarea crea su propio cliente SNMP, asi un host que falla al crear la sesion
    (por ejemplo un nombre que no resuelve DNS) solo afecta a ese host.
    """
    tareas: list[Tarea] = [
        (f"humedad {c.HOST_NAME_HUMEDAD}", partial(_tarea_humedad, ajustes_snmp)),
        (f"DC {c.HOST_NAME_DC}", partial(_tarea_dc, ajustes_snmp)),
    ]
    tareas += [
        (
            f"state {host}",
            partial(_tarea_state, host, ajustes_snmp, notificador, repo_db, fallas_para_alerta),
        )
        for host in c.HOST_NAME_STATE
    ]
    return tareas


def _ejecutar_protegido(nombre: str, tarea: Callable[[], list[str]]) -> ResultadoTarea:
    """
    Ejecuta una tarea y devuelve sus lineas. Si lanza una excepcion la registra (con traceback)
    y devuelve None, asi un driver que falla no frena a los demas.
    """
    try:
        return tarea()
    except Exception:
        logger.exception("Error al ejecutar %s", nombre)
        return None


def ejecutar_tareas(tareas: list[Tarea], max_workers: int) -> list[ResultadoTarea]:
    """
    Ejecuta todas las tareas en un pool de hilos (humedad y DC incluidos: asi sus timeouts no
    se suman al resto). Devuelve un resultado por tarea, en el orden de las tareas (no en el que
    terminan): sus lineas (list[str]) o None si lanzo una excepcion.
    Las tareas no escriben en stdout: los resultados vuelven al hilo principal por los futures.
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_ejecutar_protegido, nombre, tarea) for nombre, tarea in tareas]
    return [future.result() for future in futures]


def escribir_lineas(lineas: list[str]) -> None:
    """
    Escribe todas las lineas en stdout con una sola escritura, desde el hilo principal.
    Si cada hilo hiciera su propio print, el texto de una linea y su salto de linea podrian
    intercalarse con los de otra y generar line protocol invalido.
    """
    if lineas:
        sys.stdout.write("\n".join(lineas) + "\n")
        sys.stdout.flush()


def main(entorno: Entorno) -> int:
    """
    Devuelve el codigo de salida del proceso:
    - 0 si se obtuvo al menos una metrica. Telegraf descarta toda la salida si el codigo no es 0,
      asi que las tareas que fallan se registran en el log pero no tiran abajo las demas metricas.
    - 1 si no hay ninguna metrica (fallaron todas las tareas o no respondio ningun equipo).
    """
    logger.info("Iniciando monitoreo UPS")

    # Infraestructura compartida: si falla es un error fatal (configuracion local rota)
    notificador = Notificador(entorno.webhook_url, entorno.http_timeout)
    repo_db = RepositorioDB(entorno.archivo_db)

    tareas = crear_tareas(entorno.snmp, notificador, repo_db, entorno.fallas_para_alerta)
    resultados = ejecutar_tareas(tareas, entorno.max_workers)

    lineas = [linea for resultado in resultados if resultado for linea in resultado]
    escribir_lineas(lineas)

    fallidas = resultados.count(None)
    if fallidas:
        logger.warning("Fallaron %d de %d tareas", fallidas, len(resultados))
    if not lineas:
        logger.error("No se obtuvo ninguna metrica")
        return 1
    return 0


def iniciar(ruta_env: str | None = c.ARCHIVO_ENV) -> int:
    """
    Punto de entrada del programa. Primero carga la configuracion del entorno, despues configura
    el logging con ella y recien ahi ejecuta el monitoreo. Devuelve el codigo de salida.
    """
    try:
        entorno = cargar_entorno(ruta_env)
    except ErrorConfiguracion as e:
        # Todavia no hay logger (su carpeta y nivel vienen de la configuracion): va a stderr,
        # que Telegraf muestra en su log cuando el comando termina con error
        sys.stderr.write(f"Configuracion invalida (revisar el .env):\n{e}\n")
        return 1

    warnings.filterwarnings("ignore", category=UserWarning)
    configurar_logger(entorno.logs_dir, entorno.log_level)
    try:
        return main(entorno)
    except Exception:
        # El traceback ya queda en el archivo de log, no hace falta relanzar la excepcion
        logger.exception("Error fatal en el flujo principal")
        return 1


if __name__ == "__main__":
    # Se configura recien al ejecutar: asi importar main (por ejemplo en los tests)
    # no tiene efectos secundarios
    sys.exit(iniciar())
