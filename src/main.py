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


def _tarea_humedad():
    cliente = ClienteSNMP(c.HOST_NAME_HUMEDAD)
    HumedadUPS(hostname=c.HOST_NAME_HUMEDAD, clienteSNMP=cliente).ejecutar(c.OID_HUMEDAD)


def _tarea_dc():
    cliente = ClienteSNMP(c.HOST_NAME_DC)
    DataCenterUPS(c.HOST_NAME_DC, clienteSNMP=cliente).ejecutar(c.OID_DC)


def _tarea_state(host, notificador, repo_db):
    cliente = ClienteSNMP(host)
    StateUPS(hostname=host, clienteSNMP=cliente, notificador=notificador, rep_db=repo_db).ejecutar(
        c.OID_UPS, c.OIDT, c.OIDTNEW
    )


def crear_tareas(notificador, repo_db):
    """
    Arma las tareas a ejecutar como listas de (nombre, funcion).
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
    Ejecuta una tarea. Si lanza una excepcion la registra (con traceback) y devuelve False,
    asi un driver que falla no frena a los demas.
    """
    try:
        tarea()
        return True
    except Exception:
        logger.exception("Error al ejecutar %s", nombre)
        return False


def ejecutar_tareas(tareas_secuenciales, tareas_paralelas, max_workers=MAX_WORKERS):
    """
    Ejecuta primero las tareas secuenciales y despues las paralelas en un pool de hilos.
    Devuelve una lista con True/False por tarea (True = termino sin excepcion).
    """
    resultados = [_ejecutar_protegido(nombre, tarea) for nombre, tarea in tareas_secuenciales]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_ejecutar_protegido, nombre, tarea)
            for nombre, tarea in tareas_paralelas
        ]
    resultados += [future.result() for future in futures]

    return resultados


def main():
    """
    Devuelve el codigo de salida del proceso:
    - 0 si al menos una tarea termino bien (telegraf toma las metricas que se imprimieron).
    - 1 si fallaron todas (no hay metricas y el error queda visible en el log de telegraf).
    Un UPS que no responde SNMP no cuenta como falla: es un caso manejado (SIN_RESPUESTA_SNMP).
    """
    logger.info("Iniciando monitoreo UPS")

    # Infraestructura compartida: si falla es un error fatal (configuracion local rota)
    notificador = Notificador(c.ARCHIVO_ENV)
    repo_db = RepositorioDB(c.ARCHIVO_DB)

    tareas_secuenciales, tareas_paralelas = crear_tareas(notificador, repo_db)
    resultados = ejecutar_tareas(tareas_secuenciales, tareas_paralelas)

    fallidas = resultados.count(False)
    if fallidas:
        logger.warning("Fallaron %d de %d tareas", fallidas, len(resultados))
    return 0 if fallidas < len(resultados) else 1


if __name__ == "__main__":
    # Se configura recien al ejecutar, asi importar main (por ejemplo en los tests) no tiene efectos secundarios
    warnings.filterwarnings("ignore", category=UserWarning)
    configurar_logger()
    try:
        codigo_salida = main()
    except Exception:
        # El traceback ya queda en el log (archivo + stderr), no hace falta relanzar la excepcion
        logger.exception("Error fatal en el flujo principal")
        codigo_salida = 1
    sys.exit(codigo_salida)
