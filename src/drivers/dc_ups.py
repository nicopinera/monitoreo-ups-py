import config.configuracion as c
from core.alertas import Datos, Numero
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
    """UPS trifasico del DC (Eaton). Por ahora solo alerta si no responde (SIN_RESPUESTA_SNMP)."""

    TIPO = "UPS trifásico DC"

    def obtener_datos(self) -> Datos:
        """Las metricas sin dato quedan en None. Calcula promedios y potencias por fase."""
        datos: dict[str, Numero | None] = {}
        for nombre, valor in self._leer_oids().items():
            if valor is None:
                datos[nombre] = None
            elif nombre == "autonomia":
                datos[nombre] = round(int(valor) / 60, 2)  # segundos -> minutos
            else:
                datos[nombre] = int(valor)

        fases = ["f1", "f2", "f3"]
        corrientes = [datos.get(f"corriente_out_{f}") for f in fases]
        voltajes = [datos.get(f"voltaje_out_{v}") for v in ["an", "bn", "cn"]]

        # La potencia de una fase solo se calcula si estan su tension y su corriente
        potencias_va: list[Numero | None] = [
            v * a if v is not None and a is not None else None
            for v, a in zip(voltajes, corrientes, strict=True)
        ]
        datos["potencia_va_out_a"] = potencias_va[0]
        datos["potencia_va_out_b"] = potencias_va[1]
        datos["potencia_va_out_c"] = potencias_va[2]

        # Promedio y totales solo con las tres fases, si no darian un valor falsamente bajo
        corrientes_con_dato = [a for a in corrientes if a is not None]
        if len(corrientes_con_dato) == len(fases):
            datos["corriente_prom"] = round(sum(corrientes_con_dato) / len(fases), 2)
        else:
            datos["corriente_prom"] = None

        potencias_con_dato = [p for p in potencias_va if p is not None]
        if len(potencias_con_dato) == len(fases):
            total_va = sum(potencias_con_dato)
            datos["potencia_va_out"] = total_va
            datos["potencia_w_out"] = total_va * c.FP_OUT
        else:
            datos["potencia_va_out"] = None
            datos["potencia_w_out"] = None
        return datos

    def lineas_telegraf(self, datos: Datos) -> list[str]:
        """Una linea por grupo de LINEAS_TELEGRAF; se omiten los campos y las lineas sin dato."""
        lineas = []
        for campos_linea in LINEAS_TELEGRAF:
            campos = self._formatear_campos(datos, campos_linea)
            if campos:
                lineas.append(f"dc-ups,host={self.hostname} {campos}")
        return lineas
