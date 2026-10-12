import config.configuracion as c
from core.ups_base import BaseUPS
from infraestructura.snmp_client import Numero

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
    def obtener_datos(self, oid_metricas: dict[str, str]) -> None:
        """
        Obtiene datos SNMP basado en diccionario de OIDs.
        oid_metricas: {nombre: oid_string}
        Las metricas sin dato quedan en None.
        """

        for nombre, oid in oid_metricas.items():
            valor = self.cliente_snmp.obtener_valor_numerico(oid)
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
        potencias_va: list[Numero | None] = [
            v * a if v is not None and a is not None else None
            for v, a in zip(voltajes, corrientes, strict=True)
        ]
        self.datos["potencia_va_out_a"] = potencias_va[0]
        self.datos["potencia_va_out_b"] = potencias_va[1]
        self.datos["potencia_va_out_c"] = potencias_va[2]

        # Promedio y totales solo con las tres fases, si no darian un valor falsamente bajo
        corrientes_con_dato = [a for a in corrientes if a is not None]
        if len(corrientes_con_dato) == len(fases):
            self.datos["corriente_prom"] = round(sum(corrientes_con_dato) / len(fases), 2)
        else:
            self.datos["corriente_prom"] = None

        potencias_con_dato = [p for p in potencias_va if p is not None]
        if len(potencias_con_dato) == len(fases):
            total_va = sum(potencias_con_dato)
            self.datos["potencia_va_out"] = total_va
            self.datos["potencia_w_out"] = total_va * c.FP_OUT
        else:
            self.datos["potencia_va_out"] = None
            self.datos["potencia_w_out"] = None

    def validar_datos_y_notificar(self) -> None:
        """El UPS del DC todavia no tiene alertas (M3)"""

    def lineas_telegraf(self) -> list[str]:
        """Una linea por grupo de LINEAS_TELEGRAF; se omiten los campos y las lineas sin dato."""
        lineas = []
        for campos_linea in LINEAS_TELEGRAF:
            campos = self._formatear_campos(campos_linea)
            if campos:
                lineas.append(f"dc-ups,host={self.hostname} {campos}")
        return lineas

    def ejecutar(self, oid_metricas_dc: dict[str, str]) -> list[str]:
        self.obtener_datos(oid_metricas_dc)
        return self.lineas_telegraf()
