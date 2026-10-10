#!/usr/bin/python3

import config.configuracion as c
from core.ups_base import BaseUPS

# Cada tupla es una linea de telegraf con sus campos, en el orden en que se imprimen
LINEAS_TELEGRAF = (
    ("autonomia",),
    ("carga_bat",),
    ("bat_temp",),
    ("carga_out",),
    ("corriente_out_f1", "corriente_out_f2", "corriente_out_f3", "corriente_prom"),
    ("voltaje_out", "voltaje_out_an", "voltaje_out_bn", "voltaje_out_cn"),
    ("voltaje_an_input", "voltaje_bn_input", "voltaje_cn_input"),
    (
        "potencia_va_out_a",
        "potencia_va_out_b",
        "potencia_va_out_c",
        "potencia_va_out",
        "potencia_w_out",
    ),
)


class DataCenterUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)

    def obtener_datos(self, oid_metricas):
        """
        Obtiene datos SNMP basado en diccionario de OIDs.
        oid_metricas: {nombre: oid_string}
        Las metricas sin dato quedan en None.
        """

        for nombre, oid in oid_metricas.items():
            valor = self.clienteSNMP.obtener_valor_numerico(oid)
            if valor is None:
                self.datos[nombre] = None
            elif nombre == "autonomia":
                self.datos[nombre] = round(int(valor) / 60, 2)
            else:
                self.datos[nombre] = int(valor)

        fases = ["f1", "f2", "f3"]
        corrientes = [self.datos.get(f"corriente_out_{f}") for f in fases]
        voltajes = [self.datos.get(f"voltaje_out_{v}") for v in ["an", "bn", "cn"]]

        # La potencia de una fase solo se calcula si estan su tension y su corriente
        potencias_va = [
            v * a if v is not None and a is not None else None for v, a in zip(voltajes, corrientes)
        ]
        self.datos["potencia_va_out_a"] = potencias_va[0]
        self.datos["potencia_va_out_b"] = potencias_va[1]
        self.datos["potencia_va_out_c"] = potencias_va[2]

        # Promedio y totales solo con las tres fases, si no darian un valor falsamente bajo
        if all(a is not None for a in corrientes):
            self.datos["corriente_prom"] = round(sum(corrientes) / len(corrientes), 2)
        else:
            self.datos["corriente_prom"] = None

        if all(p is not None for p in potencias_va):
            total_va = sum(potencias_va)
            self.datos["potencia_va_out"] = total_va
            self.datos["potencia_w_out"] = total_va * c.FP_OUT
        else:
            self.datos["potencia_va_out"] = None
            self.datos["potencia_w_out"] = None

    def validar_datos_y_notificar(self):
        """Cada driver tiene sus propia logica para validar y generar las alertas"""
        pass

    def imprimir_telegraf(self):
        """Cada driver imprime su formato para grafana/telegraf. Los campos sin dato se omiten."""
        for campos_linea in LINEAS_TELEGRAF:
            campos = self._formatear_campos(campos_linea)
            if campos:
                print(f"dc-ups,host={self.hostname} {campos}")

    def ejecutar(self, oid_metricas_dc):
        self.obtener_datos(oid_metricas_dc)
        self.imprimir_telegraf()
