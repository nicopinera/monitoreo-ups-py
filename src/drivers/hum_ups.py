from config.logger import get_logger, get_telegraf_logger
from core.ups_base import BaseUPS

logger = get_logger(__name__)
telegraf_logger = get_telegraf_logger()

class HumedadUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
    
    def obtener_datos(self,oid_hum):
        """Cada driver debe saber que OID pedir"""
        self.datos["humidity"] = self.clienteSNMP.obtener_valor(oid_hum)
    
    def validar_datos_y_notificar(self):
        """Cada driver tiene sus propia logica para validar y generar las alertas"""
        if self.datos["humidity"] == None:
            self.datos["humidity"] = 0

    def imprimir_telegraf(self):
        print(f"ups_temp2,host={self.hostname} humidity={self.datos["humidity"]}")
    
    def ejecutar(self,oid_hum):
        self.obtener_datos(oid_hum)
        self.validar_datos_y_notificar()
        self.imprimir_telegraf()