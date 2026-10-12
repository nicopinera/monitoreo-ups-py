"""Interfaz comun de los drivers (M4)"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.alertas import Chequeo, Datos, Equipo, Numero, Regla, evaluar

if TYPE_CHECKING:
    # Solo para las anotaciones: el dominio no importa la infraestructura al ejecutarse
    from infraestructura.snmp_client import ClienteSNMP


@dataclass(frozen=True)
class Lectura:
    """Lo que devuelve un driver en cada ejecucion."""

    equipo: Equipo
    lineas: list[str]  # line protocol para Telegraf
    hay_datos: bool  # False: el equipo no respondio ninguna consulta
    chequeos: list[Chequeo] = field(default_factory=list)


class BaseUPS(ABC):
    """
    Cada driver sabe que leer y como armar sus lineas de Telegraf. No envia alertas ni usa la
    base: devuelve una Lectura y el GestorAlertas decide que avisar.
    """

    TIPO = "UPS"  # como se lo nombra en los mensajes

    def __init__(
        self,
        hostname: str,
        cliente_snmp: "ClienteSNMP",
        oids: Mapping[str, str],
        reglas: Sequence[Regla] = (),
    ) -> None:
        """oids: metrica -> OID. reglas: alertas de este equipo (umbrales inyectados)."""
        self.hostname = hostname
        self.cliente_snmp = cliente_snmp
        self.oids = oids
        self.reglas = reglas

    @property
    def equipo(self) -> Equipo:
        return Equipo(hostname=self.hostname, tipo=self.TIPO, clave=self.hostname)

    @abstractmethod
    def obtener_datos(self) -> Datos:
        """Lee los OIDs del equipo. Las metricas sin dato quedan en None."""

    @abstractmethod
    def lineas_telegraf(self, datos: Datos) -> list[str]:
        """
        Arma las lineas para Telegraf. No imprime: la salida la escribe main desde el hilo
        principal (ver main.escribir_lineas).
        """

    def ejecutar(self) -> Lectura:
        """
        Lee, arma las lineas y evalua las reglas. Igual para todos los drivers: main los recorre
        sin conocer sus parametros. Un error al leer se propaga: main lo registra y sigue.
        """
        datos = self.obtener_datos()
        hay_datos = any(valor is not None for valor in datos.values())
        return Lectura(
            equipo=self.equipo,
            lineas=self.lineas_telegraf(datos) if hay_datos else [],
            hay_datos=hay_datos,
            # Si no respondio, la unica alerta posible es SIN_RESPUESTA_SNMP (la decide el gestor)
            chequeos=evaluar(self.reglas, datos) if hay_datos else [],
        )

    def _leer_oids(self) -> dict[str, Numero | None]:
        """Lee cada OID de self.oids como numero."""
        return {
            nombre: self.cliente_snmp.obtener_valor_numerico(oid)
            for nombre, oid in self.oids.items()
        }

    @staticmethod
    def _formatear_campos(datos: Datos, campos: tuple[str, ...]) -> str:
        """
        Arma los campos de una linea de telegraf ("a=1,b=2") omitiendo los que no tienen dato.
        Devuelve "" si ninguno tiene dato (una linea sin campos es invalida en line protocol).
        """
        return ",".join(
            f"{campo}={datos[campo]}" for campo in campos if datos.get(campo) is not None
        )
