from drivers.ups_base import BaseUPS

class StateUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
    
    def obtener_datos(self, oid_dicc,oidtemp,oidtemp2):
        """Cada driver debe saber que OID pedir"""
        # Temperatura bateria
        
        for nombre,oid in oid_dicc.items():
            dato_aux = self.clienteSNMP.obtener_valor(oid)
            if dato_aux:
                if nombre == 'life':
                    self.datos[nombre] = round((int(dato_aux))/6000,2)
                else:
                    self.datos[nombre] = dato_aux
        
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
        campos = ",".join([f"{k}={v}" for k, v in self.datos.items()])
        print(f"ups_temp2,host={self.hostname} {campos}")   
    
    def ejecutar(self,oid_dicc,oidtemp,oidtemp2):
        self.obtener_datos(oid_dicc,oidtemp,oidtemp2)
        self.imprimir_telegraf()