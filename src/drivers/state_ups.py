from drivers.ups_base import BaseUPS

class StateUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
    
    def obtener_datos(self, oidbateria,oidcapacidad,oidload,oidlife,oidcorriente,oidtemp,oidtemp2):
        """Cada driver debe saber que OID pedir"""
        # Temperatura bateria
        self.datos["battery"] = self.clienteSNMP.obtener_valor(oidbateria)
        
        # Capacidad bateria
        self.datos["capacity"] = self.clienteSNMP.obtener_valor(oidcapacidad)
        
        # Carga a la salida
        self.datos["load"] = self.clienteSNMP.obtener_valor(oidload)
        
        # autonomia
        t_aux = round((int(self.clienteSNMP.obtener_valor(oidlife)))/6000,2)
        self.datos["life"] = t_aux
        
        # Corriente salida
        self.datos["current"] = self.clienteSNMP.obtener_valor(oidcorriente)
        
        # I/O sensor de temperatura
        try:
            self.datos["temp"] = self.clienteSNMP.obtener_valor(oidtemp)
        except:
            self.datos["temp"] = self.clienteSNMP.obtener_valor(oidtemp2)
    
    def validar_datos_y_notificar(self):
        """Cada driver tiene sus propia logica para validar y generar las alertas"""
        pass

    def imprimir_telegraf(self):
        """Cada driver imprime su formato para grafana/telegraf"""
        print(f"ups_temp2,host={self.hostname} battery={self.datos["battery"]},temp={self.datos["temp"]},capacity={self.datos["capacity"]},load={self.datos["load"]},life={self.datos["life"]},current={self.datos["current"]}")   
    
    def ejecutar(self):
        self.obtener_datos()
        self.imprimir_telegraf()
        if self.notificador and self.rep_db:
            self.validar_datos_y_notificar()