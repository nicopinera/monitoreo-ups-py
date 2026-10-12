import logging
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager
from typing import Any

# El esquema vive junto al codigo y no en data/: data/ se monta como volumen en Docker
# y solo tiene archivos generados en ejecucion (ver A6 en el plan de mejora)
ARCHIVO_ESQUEMA = os.path.join(os.path.dirname(__file__), "schema.sql")

# Una fila de la tabla errores: (id, ups_host, tipo_error, estado_error, fecha)
Fila = tuple[Any, ...]


class RepositorioDB:
    def __init__(self, db_file: str) -> None:
        self.db_file = db_file
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

        # La carpeta de la base (data/) no esta en git: en un clon nuevo hay que crearla
        carpeta = os.path.dirname(self.db_file)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)

        # Creación inicial de tablas
        try:
            with self._conexion() as conn, open(ARCHIVO_ESQUEMA, encoding="utf-8") as esquema:
                conn.executescript(esquema.read())
                conn.commit()
        except sqlite3.Error:
            self.logger.exception("Error al ejecutar el script de creación de tablas")

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        """
        Conexion que se cierra al salir. `with sqlite3.connect(...)` solo hace commit o rollback:
        no cierra la conexion (Python 3.13 lo avisa con ResourceWarning).
        """
        with closing(sqlite3.connect(self.db_file)) as conn:
            yield conn

    def _consultar_una(self, sql: str, parametros: tuple[str, ...]) -> Fila | None:
        with self.lock, self._conexion() as conn:
            fila: Fila | None = conn.execute(sql, parametros).fetchone()
            return fila

    def _modificar(self, sql: str, parametros: tuple[str, ...]) -> None:
        with self.lock, self._conexion() as conn:
            conn.execute(sql, parametros)
            conn.commit()

    def error_activo(self, ups_host: str, tipo_error: str) -> Fila | None:
        """Busca errores activos específicos de un UPS."""
        return self._consultar_una(
            "SELECT * FROM errores WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",
            (ups_host, tipo_error),
        )

    def agregar_error(self, ups_host: str, tipo_error: str) -> None:
        """Agrega un error a la base de datos."""
        self._modificar(
            "INSERT INTO errores (ups_host, tipo_error, estado_error) VALUES (?, ?, 'activo')",
            (ups_host, tipo_error),
        )

    def error_resuelto(self, ups_host: str, tipo_error: str) -> Fila | None:
        """Busca si el último registro de un error está en estado resuelto."""
        return self._consultar_una(
            "SELECT * FROM errores"
            " WHERE ups_host=? AND tipo_error=? AND estado_error='resuelto'"
            " ORDER BY fecha DESC LIMIT 1",
            (ups_host, tipo_error),
        )

    def activar_error(self, ups_host: str, tipo_error: str) -> None:
        """Reactiva un error que estaba resuelto."""
        self._modificar(
            "UPDATE errores SET estado_error='activo', fecha=CURRENT_TIMESTAMP"
            " WHERE ups_host=? AND tipo_error=? AND estado_error='resuelto'",
            (ups_host, tipo_error),
        )

    def resolver_error(self, ups_host: str, tipo_error: str) -> None:
        """Marca un error activo como resuelto."""
        self._modificar(
            "UPDATE errores SET estado_error='resuelto', fecha=CURRENT_TIMESTAMP"
            " WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",
            (ups_host, tipo_error),
        )
