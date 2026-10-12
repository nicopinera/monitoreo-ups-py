from core.ups_base import BaseUPS


class HumedadUPS(BaseUPS):
    def obtener_datos(self, oid_hum: str) -> None:
        """Cada driver debe saber que OID pedir"""
        self.datos["humidity"] = self.cliente_snmp.obtener_valor_numerico(oid_hum)

    def validar_datos_y_notificar(self) -> None:
        """El sensor de humedad no tiene alertas por ahora"""

    def lineas_telegraf(self) -> list[str]:
        """Si no hay dato de humedad no hay linea"""
        campos = self._formatear_campos(("humidity",))
        return [f"ups_temp2,host={self.hostname} {campos}"] if campos else []

    def ejecutar(self, oid_hum: str) -> list[str]:
        self.obtener_datos(oid_hum)
        self.validar_datos_y_notificar()
        return self.lineas_telegraf()
