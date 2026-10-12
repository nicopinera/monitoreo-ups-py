from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.alertas import Datos, Numero, Regla
from core.ups_base import BaseUPS

if TYPE_CHECKING:
    from infraestructura.snmp_client import ClienteSNMP

# Orden de los campos en la linea de telegraf
CAMPOS_TELEGRAF = ("battery", "temp", "capacity", "load", "life", "current")


class StateUPS(BaseUPS):
    """UPS APC monofasico: baterias, carga, autonomia y temperatura ambiente (sensor UIO)."""

    def __init__(
        self,
        hostname: str,
        cliente_snmp: "ClienteSNMP",
        oids: Mapping[str, str],
        oids_temperatura: Sequence[str],
        reglas: Sequence[Regla] = (),
    ) -> None:
        """
        oids_temperatura: OIDs del sensor de temperatura ambiente, en orden de preferencia. Segun
        el firmware, el sensor se informa como UIO (OIDT) o como externo (OIDTNEW).
        """
        super().__init__(hostname, cliente_snmp, oids, reglas)
        self.oids_temperatura = oids_temperatura

    def obtener_datos(self) -> Datos:
        datos = self._leer_oids()

        # TimeTicks (centesimas de segundo) -> minutos
        life = datos.get("life")
        if life is not None:
            datos["life"] = round(life / 6000, 2)

        # Temperatura ambiente: el primer OID que tenga dato
        temp: Numero | None = None
        for oid in self.oids_temperatura:
            temp = self.cliente_snmp.obtener_valor_numerico(oid)
            if temp is not None:
                break
        datos["temp"] = int(temp) if temp is not None else None
        return datos

    def lineas_telegraf(self, datos: Datos) -> list[str]:
        """Una linea con los campos que tienen dato."""
        return [f"ups_temp2,host={self.hostname} {self._formatear_campos(datos, CAMPOS_TELEGRAF)}"]
