from core.alertas import Datos, Equipo
from core.ups_base import BaseUPS


class HumedadUPS(BaseUPS):
    """Sensor de humedad conectado a un UPS. Solo alerta si no responde (SIN_RESPUESTA_SNMP)."""

    TIPO = "Sensor de humedad"

    @property
    def equipo(self) -> Equipo:
        # El sensor vive en un UPS que tambien tiene su propio driver: con otra clave sus
        # incidentes y sus hilos no se mezclan con los del UPS
        return Equipo(hostname=self.hostname, tipo=self.TIPO, clave=f"{self.hostname}-humedad")

    def obtener_datos(self) -> Datos:
        return self._leer_oids()

    def lineas_telegraf(self, datos: Datos) -> list[str]:
        return [f"ups_temp2,host={self.hostname} {self._formatear_campos(datos, ('humidity',))}"]
