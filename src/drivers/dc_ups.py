from drivers.ups_base import BaseUPS

class DataCenterUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
    
    def obtener_datos(self, oid_metricas):
        """
        Obtiene datos SNMP basado en diccionario de OIDs.
        oid_metricas: {nombre: oid_string}
        """
        self.datos = {}
        
        for nombre, oid in oid_metricas.items():
            try:
                valor_raw = self.clienteSNMP.get(oid)
                self.datos[nombre] = int(valor_raw.value)
            except Exception as e:
                self.datos[nombre] = None
                if self.notificador:
                    self.notificador.notificar(f"Error obteniendo {nombre} (OID {oid}): {e}")
    
    def validar_datos_y_notificar(self):
        """Cada driver tiene sus propia logica para validar y generar las alertas"""
        pass

    def imprimir_telegraf(self):
        """Cada driver imprime su formato para grafana/telegraf"""
        # Extraer nombre corto del hostname (ej: ups-dc.psi.unc.edu.ar -> ups-dc)
        host_corto = self.hostname.split(".")[0]
        
        # Construir la línea de telegraf con todos los datos
        campos = ",".join([f"{k}={v}" for k, v in self.datos.items() if v is not None])
        print(f"ups_metrica,host={host_corto} {campos}")
    
    def ejecutar(self):
        return super().ejecutar()