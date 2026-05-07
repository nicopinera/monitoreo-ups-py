#!/usr/bin/python3

import sqlite3
import threading
import config.configuracion as c
from config.logger import get_logger

logger = get_logger(__name__)

class RepositorioDB:
    def __init__(self, db_file):
        self.db_file = db_file
        self.lock = threading.Lock()
        
        # Creación inicial de tablas
        try:
            with sqlite3.connect(self.db_file) as conn:
                with open(c.ARCHIVO_CREACION_TABLA_STATE, 'r', encoding="utf-8") as sql_script:
                    tabla = sql_script.read()
                conn.executescript(tabla)
                conn.commit()
        except sqlite3.Error as e:
            logger.error("Error al ejecutar el script de creación de tablas", exc_info=True)

    def error_activo(self, ups_host, tipo_error):
        """Busca errores activos específicos de un UPS."""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM errores WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",
                    (ups_host, tipo_error)
                )
                return cursor.fetchone()

    def agregar_error(self, ups_host, tipo_error):
        """Agrega un error a la base de datos."""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO errores (ups_host, tipo_error, estado_error) VALUES (?, ?, 'activo')",
                    (ups_host, tipo_error)
                )
                conn.commit()

    def error_resuelto(self, ups_host, tipo_error):
        """Busca si el último registro de un error está en estado resuelto."""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM errores WHERE ups_host=? AND tipo_error=? AND estado_error='resuelto' ORDER BY fecha DESC LIMIT 1",
                    (ups_host, tipo_error)
                )
                return cursor.fetchone()

    def activar_error(self, ups_host, tipo_error):
        """Reactiva un error que estaba resuelto."""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE errores SET estado_error='activo', fecha=CURRENT_TIMESTAMP WHERE ups_host=? AND tipo_error=? AND estado_error='resuelto'",
                    (ups_host, tipo_error)
                )
                conn.commit()

    def resolver_error(self, ups_host, tipo_error):
        """Marca un error activo como resuelto."""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE errores SET estado_error='resuelto', fecha=CURRENT_TIMESTAMP WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",
                    (ups_host, tipo_error)
                )
                conn.commit()