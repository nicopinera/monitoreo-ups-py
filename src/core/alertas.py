"""
Reglas de alerta y eventos, sin formato ni infraestructura (M6).

Las reglas son datos (metrica, condicion, umbral, unidad): los umbrales se definen en
config/configuracion.py y se inyectan a cada driver. El texto de los mensajes lo arma la
infraestructura (infraestructura/formato_chat.py).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.errores import Errores

# Valor numerico de una metrica (int o float, como lo devuelve ClienteSNMP)
Numero = int | float

# Datos de una lectura: metrica -> valor, None si el equipo no lo informo
Datos = Mapping[str, Numero | None]


@dataclass(frozen=True)
class Regla:
    """
    Alerta `error` cuando la metrica supera el umbral:
    - "max": valor > umbral (por ejemplo, carga de salida maxima)
    - "min": valor < umbral (por ejemplo, carga de bateria minima)
    """

    metrica: str
    error: Errores
    condicion: Literal["max", "min"]
    umbral: Numero
    unidad: str

    def en_alerta(self, valor: Numero) -> bool:
        return valor > self.umbral if self.condicion == "max" else valor < self.umbral


@dataclass(frozen=True)
class Chequeo:
    """Resultado de evaluar una regla en esta ejecucion, con el valor leido."""

    regla: Regla
    valor: Numero
    en_alerta: bool


def evaluar(reglas: Iterable[Regla], datos: Datos) -> list[Chequeo]:
    """
    Evalua las reglas cuyas metricas tienen dato. Una metrica sin dato no genera chequeo: su
    error no se activa ni se resuelve, queda como estaba (un dato faltante no es un "todo bien").
    """
    chequeos = []
    for regla in reglas:
        valor = datos.get(regla.metrica)
        if valor is not None:
            chequeos.append(Chequeo(regla, valor, regla.en_alerta(valor)))
    return chequeos


@dataclass(frozen=True)
class Equipo:
    """
    Identidad de un equipo para las alertas.
    - clave: identifica sus incidentes en la base y sus hilos en el chat. Es el hostname, salvo
      que un mismo host tenga dos drivers (el sensor de humedad vive en un UPS).
    - tipo: como se lo nombra en los mensajes ("UPS", "Sensor de humedad").
    """

    hostname: str
    tipo: str
    clave: str


@dataclass(frozen=True)
class Evento:
    """
    Cambio de estado de un error, para notificar: se abrio un incidente o se cerro.
    Fechas en UTC. `inicio` identifica al incidente (y a su hilo en el chat).
    """

    equipo: Equipo
    error: Errores
    accion: Literal["abrir", "cerrar"]
    inicio: datetime
    fin: datetime | None = None  # solo al cerrar
    chequeo: Chequeo | None = None  # valor y umbral, si el error sale de una regla
    fallas: int | None = None  # ejecuciones seguidas sin respuesta (SIN_RESPUESTA_SNMP)
