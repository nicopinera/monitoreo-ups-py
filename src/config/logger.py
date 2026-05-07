import logging
from logging.handlers import RotatingFileHandler
import os
import config.configuracion as c


def ensure_logs_dir():
    """Creacion de la carpeta para almacenar los logs"""
    os.makedirs(c.LOGS_DIR, exist_ok=True)


def setup_root_logger():
    ensure_logs_dir()
    #Al no pasarle nombre configura el logger raiz, que es el padre de todos los loggers. 
    # Esto hace que cualquier logger que se cree en la aplicación herede esta configuración.
    logger = logging.getLogger()

    #Esto para evitar que hayan handlers duplicados si se llama varias veces a get_logger()
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # A diferencia del FileHandler simple, este no llena el disco. 
    # Cuando el archivo app.log llega a 10MB, se cierra.
    # backupCount=5; El sistema renombra el viejo a app.log.1, app.log.2... y así hasta 5. CUando llega al 6 borra el mas viejo
    app_handler = RotatingFileHandler(c.APP_LOG_FILE, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(c.ERROR_LOG_FILE, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    logger.addHandler(app_handler)
    logger.addHandler(error_handler)

    return logger


def get_logger(name=None):
    """Obtener loger"""
    setup_root_logger()
    return logging.getLogger(name)


# crea un logger totalmente independiente para Telegraf:
def get_telegraf_logger():
    ensure_logs_dir()
    name = "telegraf"
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    # Evita que los mensajes de Telegraf se suban al "Root Logger".
    # Así, lo que pase en Telegraf no se guardará en app.log ni en errors.log, solo irá a su propio destino (en este caso, la consola).
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    return logger
