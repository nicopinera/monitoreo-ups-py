#!/usr/bin/python3

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import config.configuracion as c

FORMATO_LOG = "%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s"


def _nivel_desde_texto(texto):
    """Convierte "DEBUG", "info", etc. al nivel de logging. Si no es valido usa INFO."""
    nivel = logging.getLevelName(str(texto).upper())
    return nivel if isinstance(nivel, int) else logging.INFO


def configurar_logger(log_dir=None, nivel=None):
    """
    Configura el logging global del proceso:
    - Archivo rotativo <log_dir>/monitoreo.log con todos los mensajes desde `nivel`.
    - stderr solo con WARNING o superior.
    stdout NO se usa: queda reservado para las lineas que lee telegraf.

    log_dir: carpeta de logs. Por defecto la variable de entorno MONITOREO_LOG_DIR o c.LOGS_DIR.
    nivel: nivel minimo del archivo. Por defecto la variable de entorno LOG_LEVEL o INFO.
    """
    log_dir = log_dir or os.getenv(c.VAR_LOG_DIR) or c.LOGS_DIR
    nivel = _nivel_desde_texto(nivel or os.getenv(c.VAR_LOG_LEVEL) or "INFO")
    formato = logging.Formatter(FORMATO_LOG)

    handler_stderr = logging.StreamHandler(sys.stderr)
    handler_stderr.setLevel(logging.WARNING)
    handler_stderr.setFormatter(formato)
    handlers = [handler_stderr]

    # Si no se puede escribir el archivo se sigue solo con stderr: el logging nunca debe frenar el monitoreo
    error_archivo = None
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler_archivo = RotatingFileHandler(
            os.path.join(log_dir, c.NOMBRE_ARCHIVO_LOG),
            maxBytes=c.LOG_MAX_BYTES,
            backupCount=c.LOG_CANTIDAD_BACKUPS,
            encoding="utf-8",
        )
        handler_archivo.setFormatter(formato)
        handlers.append(handler_archivo)
    except OSError as e:
        error_archivo = e

    logging.basicConfig(level=nivel, handlers=handlers, force=True)

    if error_archivo:
        logging.getLogger(__name__).warning(
            "No se pudo abrir el archivo de log en %s (%s), se sigue solo con stderr",
            log_dir,
            error_archivo,
        )
