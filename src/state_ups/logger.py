# logger.py
import logging
import sys

def setup_logger(name, log_file='ups_monitor.log'):
    """Configurar logger para el sistema"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Handler para archivo
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formato
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger