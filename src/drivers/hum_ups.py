from drivers.ups_base import BaseUPS

class HumedadUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
    
    def obtener_datos(self,oid_hum):
        """Cada driver debe saber que OID pedir"""
        hum = self.clienteSNMP.obtener_valor(oid_hum)
        self.datos["humidity"] = hum
    
    def validar_datos_y_notificar(self):
        """Cada driver tiene sus propia logica para validar y generar las alertas"""
        pass

    def imprimir_telegraf(self):
        print(f"ups_temp2,host={self.hostname} humidity={self.datos["humidity"]}")
    
    def ejecutar(self,oid_hum):
        self.obtener_datos(oid_hum)
        self.imprimir_telegraf()