"""Interfaz de UPS"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Solo para las anotaciones: el dominio no importa la infraestructura al ejecutarse
    from infraestructura.database import RepositorioDB
    from infraestructura.notificador import Notificador
    from infraestructura.snmp_client import ClienteSNMP, Numero


class BaseUPS(ABC):
    def __init__(
        self,
        hostname: str,
        cliente_snmp: "ClienteSNMP",
        notificador: "Notificador | None" = None,
        rep_db: "RepositorioDB | None" = None,
    ) -> None:
        self.hostname = hostname
        self.cliente_snmp = cliente_snmp
        self.notificador = notificador
        self.rep_db = rep_db
        self.datos: dict[str, Numero | None] = {}

    # obtener_datos y ejecutar reciben parametros distintos en cada driver. `*args: Any,
    # **kwargs: Any` le indica a mypy que cada driver define los suyos. Se unifica en M4.

    @abstractmethod
    def obtener_datos(self, *args: Any, **kwargs: Any) -> None:
        """Cada driver debe saber que OID pedir"""

    @abstractmethod
    def validar_datos_y_notificar(self) -> None:
        """Cada driver tiene sus propia logica para validar y generar las alertas"""

    @abstractmethod
    def lineas_telegraf(self) -> list[str]:
        """
        Cada driver arma sus lineas para grafana/telegraf y las devuelve como lista de str.
        No imprime: la salida la escribe main desde el hilo principal (ver main.escribir_lineas).
        """

    @abstractmethod
    def ejecutar(self, *args: Any, **kwargs: Any) -> list[str]:
        """Lee, valida y devuelve las lineas de telegraf del equipo."""

    def _formatear_campos(self, campos: tuple[str, ...]) -> str:
        """
        Arma los campos de una linea de telegraf ("a=1,b=2") omitiendo los que no tienen dato.
        Devuelve "" si ninguno tiene dato (una linea sin campos es invalida en line protocol).
        """
        return ",".join(
            f"{campo}={self.datos[campo]}" for campo in campos if self.datos.get(campo) is not None
        )
