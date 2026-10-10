#!/usr/bin/python3

from core.ups_base import BaseUPS


class HumedadUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)

    def obtener_datos(self, oid_hum):
        """Cada driver debe saber que OID pedir"""
        self.datos["humidity"] = self.clienteSNMP.obtener_valor_numerico(oid_hum)

    def validar_datos_y_notificar(self):
        """El sensor de humedad no tiene alertas por ahora"""
        pass

    def lineas_telegraf(self):
        """Si no hay dato de humedad no hay linea"""
        campos = self._formatear_campos(("humidity",))
        return [f"ups_temp2,host={self.hostname} {campos}"] if campos else []

    def ejecutar(self, oid_hum):
        self.obtener_datos(oid_hum)
        self.validar_datos_y_notificar()
        return self.lineas_telegraf()
