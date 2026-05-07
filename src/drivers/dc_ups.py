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
        print(f"dc-ups,host={self.hostname} autonomia={self.datos['autonomia']}")
        print(f"dc-ups,host={self.hostname} carga_bat={self.datos['carga_bat']}")
        print(f"dc-ups,host={self.hostname} bat_temp={self.datos['bat_temp']}")
        print(f"dc-ups,host={self.hostname} carga_out={self.datos['carga_out']}")
        print(f"dc-ups,host={self.hostname} corriente_out_f1={self.datos['corriente_out_f1']},corriente_out_f2={self.datos['corriente_out_f2']},corriente_out_f3={self.datos['corriente_out_f3']},corriente_prom={self.datos["corriente_prom"]}")
        print(f"dc-ups,host={self.hostname} voltaje_out={self.datos['voltaje_out']},voltaje_out_an={self.datos['voltaje_out_an']},voltaje_out_bn={self.datos['voltaje_out_bn']},voltaje_out_cn={self.datos['voltaje_out_cn']}")
        print(f"dc-ups,host={self.hostname} voltaje_an_input={self.datos['voltaje_an_input']},voltaje_bn_input={self.datos['voltaje_bn_input']},voltaje_cn_input={self.datos['voltaje_cn_input']}")
        print(f"dc-ups,host={self.hostname} potencia_va_out_a={self.datos['potencia_va_out_a']},potencia_va_out_b={self.datos['potencia_va_out_b']},potencia_va_out_c={self.datos['potencia_va_out_c']},potencia_va_out={self.datos['potencia_va_out']},potencia_w_out={self.datos['potencia_w_out']}")
    
    def ejecutar(self,oid_metricas_dc):
        self.obtener_datos(oid_metricas_dc)
        self.imprimir_telegraf()