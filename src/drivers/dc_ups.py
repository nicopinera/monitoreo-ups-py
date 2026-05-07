#!/usr/bin/python3

from config.logger import get_logger, get_telegraf_logger
from core.ups_base import BaseUPS
import config.configuracion as c

logger = get_logger(__name__)
telegraf_logger = get_telegraf_logger()

class DataCenterUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
    
    def obtener_datos(self, oid_metricas):
        """
        Obtiene datos SNMP basado en diccionario de OIDs.
        oid_metricas: {nombre: oid_string}
        """
        
        for nombre, oid in oid_metricas.items():
            valor_raw = self.clienteSNMP.obtener_valor(oid)
            if valor_raw:
                if nombre == "autonomia":
                    self.datos[nombre] = round(int(valor_raw)/60,2)
                else:
                    self.datos[nombre] = int(valor_raw)
            else:
                self.datos[nombre] = 0
        
        fases = ["f1","f2","f3"]
        corrientes = [self.datos.get(f'corriente_out_{f}',0) for f in fases]
        voltajes = [self.datos.get(f'voltaje_out_{v}',0) for v in ['an','bn','cn']]
        
        potencias_va = [v*a for v,a in zip(voltajes,corrientes)]
        total_va = sum(potencias_va)
        
        self.datos['corriente_prom'] = round(sum(corrientes)/len(corrientes),2)
        self.datos['potencia_va_out'] = total_va
        self.datos['potencia_w_out'] = total_va * c.FP_OUT
        self.datos['potencia_va_out_a'] = potencias_va[0]
        self.datos['potencia_va_out_b'] = potencias_va[1]
        self.datos['potencia_va_out_c'] = potencias_va[2]

    
    def validar_datos_y_notificar(self):
        """Cada driver tiene sus propia logica para validar y generar las alertas"""
        pass

    def imprimir_telegraf(self):
        """Cada driver imprime su formato para grafana/telegraf"""
        
        # Construir la línea de telegraf con todos los datos
        campos = ",".join([f"{k}={v}" for k, v in self.datos.items()])
        telegraf_logger.info(f"dc-ups,host={self.hostname} {campos}")
    
    def ejecutar(self,oid_metricas_dc):
        self.obtener_datos(oid_metricas_dc)
        self.imprimir_telegraf()