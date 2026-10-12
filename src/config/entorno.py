"""
Configuracion que depende del entorno (secretos, rutas, timeouts, nivel de log).

Se carga una sola vez al arrancar, desde las variables de entorno del proceso y el archivo
.env de la raiz del repo, y se pasa como parametro a cada componente: ningun otro modulo lee
variables de entorno. Lo que no depende del entorno (hosts, OIDs, umbrales) vive en
config/configuracion.py y se cambia por MR.
"""

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

from dotenv import dotenv_values

import config.configuracion as c

# Nombres de las variables de entorno (documentadas en .env.example)
VAR_WEBHOOK_URL = "GOOGLE_CHAT_WEBHOOK_URL"
VAR_SNMP_COMMUNITY = "SNMP_COMMUNITY"
VAR_SNMP_TIMEOUT = "SNMP_TIMEOUT"
VAR_SNMP_RETRIES = "SNMP_RETRIES"
VAR_HTTP_TIMEOUT = "HTTP_TIMEOUT"
VAR_MAX_WORKERS = "MAX_WORKERS"
VAR_LOG_LEVEL = "LOG_LEVEL"
VAR_DATA_DIR = "MONITOREO_DATA_DIR"

# Valores por defecto de las variables opcionales
# Un OID sin respuesta cuesta SNMP_TIMEOUT * (1 + SNMP_RETRIES) segundos (2 s por defecto).
# Ademas, despues del primer timeout no se consultan mas OIDs de ese host (ver ClienteSNMP).
SNMP_TIMEOUT_DEFECTO = 1.0  # segundos por intento
SNMP_RETRIES_DEFECTO = 1
HTTP_TIMEOUT_DEFECTO = 10.0  # segundos maximos para enviar un mensaje a Google Chat
MAX_WORKERS_DEFECTO = 13  # hilos en paralelo: casi todo el tiempo esperan la red
LOG_LEVEL_DEFECTO = "INFO"
DATA_DIR_DEFECTO = "data"  # base errores.db y carpeta logs/

NIVELES_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

N = TypeVar("N", int, float)


class ErrorConfiguracion(Exception):
    """Algun valor del entorno falta o es invalido. El mensaje lista todos los problemas."""


@dataclass(frozen=True)
class AjustesSNMP:
    community: str
    timeout: float
    retries: int


@dataclass(frozen=True)
class Entorno:
    webhook_url: str | None  # None: las alertas quedan pendientes hasta configurarlo (A8)
    snmp: AjustesSNMP
    http_timeout: float
    max_workers: int
    log_level: int
    data_dir: str  # ruta absoluta

    @property
    def archivo_db(self) -> str:
        return os.path.join(self.data_dir, "errores.db")

    @property
    def logs_dir(self) -> str:
        return os.path.join(self.data_dir, "logs")


class _Lector:
    """Lee y convierte las variables, juntando todos los errores para informarlos juntos."""

    def __init__(self, valores: Mapping[str, str]) -> None:
        self.valores = valores
        self.errores: list[str] = []

    def texto(self, nombre: str) -> str | None:
        """Valor sin espacios alrededor; None si no esta o esta vacio."""
        valor = self.valores.get(nombre, "").strip()
        return valor or None

    def obligatorio(self, nombre: str) -> str:
        valor = self.texto(nombre)
        if valor is None:
            self.errores.append(f"{nombre}: falta y es obligatoria")
            return ""
        return valor

    def numero(self, nombre: str, convertir: Callable[[str], N], defecto: N, minimo: N) -> N:
        texto = self.texto(nombre)
        if texto is None:
            return defecto
        try:
            valor = convertir(texto)
        except ValueError:
            tipo = "un entero" if convertir is int else "un numero"
            self.errores.append(f"{nombre}={texto!r}: tiene que ser {tipo}")
            return defecto
        if valor < minimo:
            self.errores.append(f"{nombre}={texto!r}: tiene que ser mayor o igual a {minimo}")
            return defecto
        return valor


def cargar_entorno(
    ruta_env: str | None = c.ARCHIVO_ENV, entorno: Mapping[str, str] | None = None
) -> Entorno:
    """
    Arma la configuracion a partir de `entorno` (por defecto las variables del proceso) y del
    archivo `ruta_env`. Si una variable esta en los dos, gana la del entorno: asi una variable
    definida a mano, o la que pasa Docker, no la pisa el .env.
    Lanza ErrorConfiguracion con todos los problemas juntos si algun valor es invalido.
    """
    del_archivo = dotenv_values(ruta_env) if ruta_env and os.path.isfile(ruta_env) else {}
    valores = {clave: valor for clave, valor in del_archivo.items() if valor is not None}
    valores.update(os.environ if entorno is None else entorno)
    lector = _Lector(valores)

    webhook_url = lector.texto(VAR_WEBHOOK_URL)
    if webhook_url is not None and not webhook_url.startswith("https://"):
        lector.errores.append(f"{VAR_WEBHOOK_URL}: tiene que empezar con https://")

    snmp = AjustesSNMP(
        community=lector.obligatorio(VAR_SNMP_COMMUNITY),
        timeout=lector.numero(VAR_SNMP_TIMEOUT, float, SNMP_TIMEOUT_DEFECTO, 0.1),
        retries=lector.numero(VAR_SNMP_RETRIES, int, SNMP_RETRIES_DEFECTO, 0),
    )
    http_timeout = lector.numero(VAR_HTTP_TIMEOUT, float, HTTP_TIMEOUT_DEFECTO, 1.0)
    max_workers = lector.numero(VAR_MAX_WORKERS, int, MAX_WORKERS_DEFECTO, 1)

    nombre_nivel = (lector.texto(VAR_LOG_LEVEL) or LOG_LEVEL_DEFECTO).upper()
    if nombre_nivel not in NIVELES_LOG:
        lector.errores.append(
            f"{VAR_LOG_LEVEL}={nombre_nivel!r}: tiene que ser uno de {NIVELES_LOG}"
        )
        nombre_nivel = LOG_LEVEL_DEFECTO

    # Una ruta relativa se toma desde la raiz del repo, no desde la carpeta donde se ejecuta
    # el proceso (Telegraf suele ejecutar desde /, Docker desde /app)
    data_dir = lector.texto(VAR_DATA_DIR) or DATA_DIR_DEFECTO
    data_dir = os.path.normpath(os.path.join(c.RUTA_RAIZ, data_dir))

    if lector.errores:
        raise ErrorConfiguracion("\n".join(f"- {error}" for error in lector.errores))

    return Entorno(
        webhook_url=webhook_url,
        snmp=snmp,
        http_timeout=http_timeout,
        max_workers=max_workers,
        log_level=int(getattr(logging, nombre_nivel)),  # "INFO" -> logging.INFO
        data_dir=data_dir,
    )
