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
    Configura el logging global del proceso: todo va al archivo rotativo
    <log_dir>/monitoreo.log desde `nivel`. No se escribe nada por consola:
    - stdout queda reservado para las lineas que lee telegraf.
    - stderr solo se usa como respaldo, si no se puede abrir el archivo (desde WARNING).

    log_dir: carpeta de logs. Por defecto la variable de entorno MONITOREO_LOG_DIR o c.LOGS_DIR.
    nivel: nivel minimo del archivo. Por defecto la variable de entorno LOG_LEVEL o INFO.
    """
    log_dir = log_dir or os.getenv(c.VAR_LOG_DIR) or c.LOGS_DIR
    nivel = _nivel_desde_texto(nivel or os.getenv(c.VAR_LOG_LEVEL) or "INFO")
    formato = logging.Formatter(FORMATO_LOG)

    # Si no se puede escribir el archivo se sigue con stderr: el logging nunca debe frenar
    # el monitoreo, y sin el archivo los errores no quedarian en ningun lado
    error_archivo = None
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(log_dir, c.NOMBRE_ARCHIVO_LOG),
            maxBytes=c.LOG_MAX_BYTES,
            backupCount=c.LOG_CANTIDAD_BACKUPS,
            encoding="utf-8",
        )
    except OSError as e:
        error_archivo = e
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
    handler.setFormatter(formato)

    logging.basicConfig(level=nivel, handlers=[handler], force=True)

    if error_archivo:
        logging.getLogger(__name__).warning(
            "No se pudo abrir el archivo de log en %s (%s), se sigue solo con stderr",
            log_dir,
            error_archivo,
        )
