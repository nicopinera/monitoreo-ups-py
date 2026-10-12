import logging
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

# El esquema vive junto al codigo y no en data/: data/ se monta como volumen en Docker
# y solo tiene archivos generados en ejecucion (ver A6 en el plan de mejora)
ARCHIVO_ESQUEMA = os.path.join(os.path.dirname(__file__), "schema.sql")

# Segundos que una conexion espera a que otro proceso libere la base antes de fallar con
# "database is locked" (por ejemplo, Telegraf y una ejecucion manual al mismo tiempo)
TIMEOUT_BLOQUEO = 10.0


@dataclass(frozen=True)
class Incidente:
    """Un error abierto: avisado y todavia no resuelto. inicio es UTC (cuando se aviso)."""

    id: int
    ups_host: str
    tipo_error: str
    inicio: datetime


# Formato de las fechas en la base: el de CURRENT_TIMESTAMP de SQLite, en UTC y sin zona
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _fecha_utc(texto: str) -> datetime:
    """'2026-10-12 20:15:01' de la base (UTC sin zona) -> datetime con zona UTC."""
    return datetime.fromisoformat(texto).replace(tzinfo=UTC)


def _texto_utc(fecha: datetime) -> str:
    """datetime (con zona) -> texto UTC de la base."""
    return fecha.astimezone(UTC).strftime(FORMATO_FECHA)


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
        with closing(sqlite3.connect(self.db_file, timeout=TIMEOUT_BLOQUEO)) as conn:
            yield conn

    def _modificar(self, sql: str, parametros: tuple[str, ...]) -> None:
        with self.lock, self._conexion() as conn:
            conn.execute(sql, parametros)
            conn.commit()

    # ------------------------------------------------------------------ incidentes

    def incidente_abierto(self, ups_host: str, tipo_error: str) -> Incidente | None:
        """El incidente abierto de ese error en ese equipo, o None si el error no esta activo."""
        with self.lock, self._conexion() as conn:
            fila = conn.execute(
                "SELECT id, ups_host, tipo_error, inicio FROM incidentes"
                " WHERE ups_host=? AND tipo_error=? AND fin IS NULL",
                (ups_host, tipo_error),
            ).fetchone()
        if fila is None:
            return None
        id_, host, tipo, inicio = fila
        return Incidente(id=id_, ups_host=host, tipo_error=tipo, inicio=_fecha_utc(inicio))

    def abrir_incidente(self, ups_host: str, tipo_error: str, inicio: datetime) -> None:
        """
        Abre un incidente. Si ya hay uno abierto de ese error no hace nada.
        inicio lo fija quien avisa: identifica al incidente y a su hilo en el chat.
        """
        self._modificar(
            "INSERT INTO incidentes (ups_host, tipo_error, inicio) VALUES (?, ?, ?)"
            " ON CONFLICT (ups_host, tipo_error) WHERE fin IS NULL DO NOTHING",
            (ups_host, tipo_error, _texto_utc(inicio)),
        )

    def cerrar_incidente(self, ups_host: str, tipo_error: str, fin: datetime) -> None:
        """Cierra el incidente abierto de ese error. Si no hay ninguno no hace nada."""
        self._modificar(
            "UPDATE incidentes SET fin=? WHERE ups_host=? AND tipo_error=? AND fin IS NULL",
            (_texto_utc(fin), ups_host, tipo_error),
        )

    # ------------------------------------------------------------------ fallas consecutivas

    def sumar_falla(self, ups_host: str, tipo_error: str) -> int:
        """Suma una ejecucion seguida con ese error y devuelve cuantas lleva."""
        with self.lock, self._conexion() as conn:
            (cantidad,) = conn.execute(
                "INSERT INTO fallas_consecutivas (ups_host, tipo_error, cantidad) VALUES (?, ?, 1)"
                " ON CONFLICT (ups_host, tipo_error) DO UPDATE SET cantidad = cantidad + 1"
                " RETURNING cantidad",
                (ups_host, tipo_error),
            ).fetchone()
            conn.commit()
        return int(cantidad)

    def reiniciar_fallas(self, ups_host: str, tipo_error: str) -> None:
        """El error no se detecto en esta ejecucion: la cuenta vuelve a empezar."""
        self._modificar(
            "DELETE FROM fallas_consecutivas WHERE ups_host=? AND tipo_error=?",
            (ups_host, tipo_error),
        )
