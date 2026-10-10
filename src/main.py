#!/usr/bin/python3

import logging
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import config.configuracion as c
from drivers.dc_ups import DataCenterUPS
from drivers.hum_ups import HumedadUPS
from drivers.state_ups import StateUPS
from infraestructura.database import RepositorioDB
from infraestructura.logger import configurar_logger
from infraestructura.notificador import Notificador
from infraestructura.snmp_client import ClienteSNMP

logger = logging.getLogger(__name__)

MAX_WORKERS = 6


# Cada tarea devuelve las lineas de telegraf de su equipo (list[str])


def _tarea_humedad():
    cliente = ClienteSNMP(c.HOST_NAME_HUMEDAD)
    return HumedadUPS(hostname=c.HOST_NAME_HUMEDAD, clienteSNMP=cliente).ejecutar(c.OID_HUMEDAD)


def _tarea_dc():
    cliente = ClienteSNMP(c.HOST_NAME_DC)
    return DataCenterUPS(c.HOST_NAME_DC, clienteSNMP=cliente).ejecutar(c.OID_DC)


def _tarea_state(host, notificador, repo_db):
    cliente = ClienteSNMP(host)
    driver = StateUPS(hostname=host, clienteSNMP=cliente, notificador=notificador, rep_db=repo_db)
    return driver.ejecutar(c.OID_UPS, c.OIDT, c.OIDTNEW)


def crear_tareas(notificador, repo_db):
    """
    Arma las tareas a ejecutar como listas de (nombre, funcion). Cada funcion devuelve sus lineas.
    Cada tarea crea su propio cliente SNMP, asi un host que falla al crear la sesion
    (por ejemplo un nombre que no resuelve DNS) solo afecta a ese host.

    Devuelve (tareas_secuenciales, tareas_paralelas).
    """
    tareas_secuenciales = [
        (f"humedad {c.HOST_NAME_HUMEDAD}", _tarea_humedad),
        (f"DC {c.HOST_NAME_DC}", _tarea_dc),
    ]
    tareas_paralelas = [
        (f"state {host}", partial(_tarea_state, host, notificador, repo_db))
        for host in c.HOST_NAME_STATE
    ]
    return tareas_secuenciales, tareas_paralelas


def _ejecutar_protegido(nombre, tarea):
    """
    Ejecuta una tarea y devuelve sus lineas. Si lanza una excepcion la registra (con traceback)
    y devuelve None, asi un driver que falla no frena a los demas.
    """
    try:
        return tarea()
    except Exception:
        logger.exception("Error al ejecutar %s", nombre)
        return None


def ejecutar_tareas(tareas_secuenciales, tareas_paralelas, max_workers=MAX_WORKERS):
    """
    Ejecuta primero las tareas secuenciales y despues las paralelas en un pool de hilos.
    Devuelve un resultado por tarea, en el orden de las tareas (no en el que terminan):
    sus lineas (list[str]) o None si lanzo una excepcion.
    Las tareas no escriben en stdout: los resultados vuelven al hilo principal por los futures.
    """
    resultados = [_ejecutar_protegido(nombre, tarea) for nombre, tarea in tareas_secuenciales]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_ejecutar_protegido, nombre, tarea)
            for nombre, tarea in tareas_paralelas
        ]
    resultados += [future.result() for future in futures]

    return resultados


def escribir_lineas(lineas):
    """
    Escribe todas las lineas en stdout con una sola escritura, desde el hilo principal.
    Si cada hilo hiciera su propio print, el texto de una linea y su salto de linea podrian
    intercalarse con los de otra y generar line protocol invalido.
    """
    if lineas:
        sys.stdout.write("\n".join(lineas) + "\n")
        sys.stdout.flush()


def main():
    """
    Devuelve el codigo de salida del proceso:
    - 0 si se obtuvo al menos una metrica. Telegraf descarta toda la salida si el codigo no es 0,
      asi que las tareas que fallan se registran en el log pero no tiran abajo las demas metricas.
    - 1 si no hay ninguna metrica (fallaron todas las tareas o no respondio ningun equipo).
    """
    logger.info("Iniciando monitoreo UPS")

    # Infraestructura compartida: si falla es un error fatal (configuracion local rota)
    notificador = Notificador(c.ARCHIVO_ENV)
    repo_db = RepositorioDB(c.ARCHIVO_DB)

    tareas_secuenciales, tareas_paralelas = crear_tareas(notificador, repo_db)
    resultados = ejecutar_tareas(tareas_secuenciales, tareas_paralelas)

    lineas = [linea for resultado in resultados if resultado for linea in resultado]
    escribir_lineas(lineas)

    fallidas = resultados.count(None)
    if fallidas:
        logger.warning("Fallaron %d de %d tareas", fallidas, len(resultados))
    if not lineas:
        logger.error("No se obtuvo ninguna metrica")
        return 1
    return 0


if __name__ == "__main__":
    # Se configura recien al ejecutar, asi importar main (por ejemplo en los tests) no tiene efectos secundarios
    warnings.filterwarnings("ignore", category=UserWarning)
    configurar_logger()
    try:
        codigo_salida = main()
    except Exception:
        # El traceback ya queda en el archivo de log, no hace falta relanzar la excepcion
        logger.exception("Error fatal en el flujo principal")
        codigo_salida = 1
    sys.exit(codigo_salida)
