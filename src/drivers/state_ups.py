import logging
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from core.errores import Errores
from core.ups_base import BaseUPS
from core.validacion import (
    Resultado,
    validar_carga,
    validar_load,
    validar_respuesta_snmp,
    validar_temp_bateria,
    validar_temp_uio,
    validar_tiempo_autonomia,
)
from infraestructura.database import RepositorioDB
from infraestructura.notificador import Notificador
from infraestructura.snmp_client import ClienteSNMP

logger = logging.getLogger(__name__)

# Cambio de estado de un error: (nombre del error, accion sobre la DB, mensaje para el chat)
Accion = Literal["agregar", "activar", "resolver"]
Transicion = tuple[str, Accion, str]

# Orden de los campos en la linea de telegraf
CAMPOS_TELEGRAF = ("battery", "temp", "capacity", "load", "life", "current")


class StateUPS(BaseUPS):
    def __init__(
        self,
        hostname: str,
        cliente_snmp: ClienteSNMP,
        notificador: Notificador,
        rep_db: RepositorioDB,
    ) -> None:
        """notificador y rep_db son obligatorios: sin ellos no se pueden gestionar las alertas."""
        super().__init__(hostname, cliente_snmp, notificador, rep_db)
        # Se redefinen sin None para que mypy sepa que siempre estan
        self.notificador: Notificador = notificador
        self.rep_db: RepositorioDB = rep_db

    def obtener_datos(self, oid_dicc: dict[str, str], oidtemp: str, oidtemp2: str) -> None:
        """Cada driver debe saber que OID pedir. Las metricas sin dato quedan en None."""
        self.datos = dict.fromkeys(CAMPOS_TELEGRAF)

        for nombre, oid in oid_dicc.items():
            valor = self.cliente_snmp.obtener_valor_numerico(oid)
            if valor is not None and nombre == "life":
                valor = round(valor / 6000, 2)
            self.datos[nombre] = valor

        # Temperatura UIO: si el OID estandar no tiene dato se prueba el alternativo
        temp_val = self.cliente_snmp.obtener_valor_numerico(oidtemp)
        if temp_val is None:
            temp_val = self.cliente_snmp.obtener_valor_numerico(oidtemp2)
        self.datos["temp"] = int(temp_val) if temp_val is not None else None

    def _hay_datos(self) -> bool:
        return any(valor is not None for valor in self.datos.values())

    def _detectar_transicion(
        self,
        hay_error: Errores | None,
        msj_error: str | None,
        nombre_error_str: str,
        transiciones: list[Transicion],
    ) -> None:
        """
        Compara el estado del sensor con el guardado en la DB, sin escribir nada.
        Si cambio, agrega a `transiciones` una tupla (nombre_error, accion, mensaje):
        - Hay error y no esta activo -> "activar" (si ya existia resuelto) o "agregar".
        - No hay error y esta activo -> "resolver".
        La DB recien se actualiza en _confirmar_transiciones, si el mensaje se pudo enviar.
        """
        error_db_activo = self.rep_db.error_activo(self.hostname, nombre_error_str)

        if hay_error and not error_db_activo:
            # Si el error ya existio y se resolvio, se reactiva esa fila; si no, se crea
            accion: Accion
            if self.rep_db.error_resuelto(self.hostname, nombre_error_str):
                accion = "activar"
            else:
                accion = "agregar"
            transiciones.append((nombre_error_str, accion, f"❌ {msj_error}"))
        elif not hay_error and error_db_activo:
            transiciones.append(
                (
                    nombre_error_str,
                    "resolver",
                    f"✅ [RESUELTO] {nombre_error_str} volvió a la normalidad.",
                )
            )

    def _confirmar_transiciones(self, transiciones: list[Transicion]) -> None:
        """Guarda en la DB las transiciones ya notificadas."""
        acciones: dict[Accion, Callable[[str, str], None]] = {
            "agregar": self.rep_db.agregar_error,
            "activar": self.rep_db.activar_error,
            "resolver": self.rep_db.resolver_error,
        }
        for nombre_error_str, accion, _mensaje in transiciones:
            acciones[accion](self.hostname, nombre_error_str)

    def _validar_metrica(
        self,
        nombre_metrica: str,
        funcion_validacion: Callable[[float], Resultado],
        error: Errores,
        transiciones: list[Transicion],
    ) -> None:
        """
        Valida una metrica y detecta si su error cambio. Si la metrica no tiene dato no se hace
        nada: el error no se activa ni se resuelve, su estado en la DB queda como estaba.
        """
        valor = self.datos.get(nombre_metrica)
        if valor is None:
            return
        err, msg = funcion_validacion(valor)
        self._detectar_transicion(err, msg, error.name, transiciones)

    def validar_datos_y_notificar(self) -> None:
        """
        Valida los datos, envia un solo mensaje con todas las transiciones del UPS y recien
        despues las guarda en la DB. Si el envio falla no se guarda nada: en la proxima
        ejecucion se detectan otra vez y se reintenta (al menos una vez, nunca se pierden).
        """
        transiciones: list[Transicion] = []

        # Respuesta SNMP: si el equipo no devolvio ningun dato no se valida nada mas
        hay_datos = self._hay_datos()
        err, msg = validar_respuesta_snmp(hay_datos)
        self._detectar_transicion(err, msg, Errores.SIN_RESPUESTA_SNMP.name, transiciones)

        if hay_datos:
            # Temperatura Baterías
            self._validar_metrica(
                "battery", validar_temp_bateria, Errores.TEMPERATURA_BATERIA_ALTA, transiciones
            )

            # Sensor Temperatura Ambiente e I/O
            temp = self.datos.get("temp")
            if temp is not None:
                err, msg = validar_temp_uio(temp)
                # Evaluamos ambos estados posibles para el sensor UIO
                self._detectar_transicion(
                    err if err == Errores.UIO_ROTO else None,
                    msg if err == Errores.UIO_ROTO else None,
                    Errores.UIO_ROTO.name,
                    transiciones,
                )
                self._detectar_transicion(
                    err if err == Errores.UIO_TEMPERATURA_ALTA else None,
                    msg if err == Errores.UIO_TEMPERATURA_ALTA else None,
                    Errores.UIO_TEMPERATURA_ALTA.name,
                    transiciones,
                )

            # Carga de las baterías
            self._validar_metrica("capacity", validar_carga, Errores.CARGA_MINIMA, transiciones)

            # Carga a la salida (Load)
            self._validar_metrica("load", validar_load, Errores.LOAD_MAXIMO, transiciones)

            # Tiempo de autonomía
            self._validar_metrica(
                "life", validar_tiempo_autonomia, Errores.AUTONOMIA_MINIMO, transiciones
            )

        if not transiciones:
            return

        encabezado = f"🔔 *Reporte de Estado: {self.hostname}*\n"
        fecha_string = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cuerpo = "\n".join(mensaje for _nombre, _accion, mensaje in transiciones)
        enviado = self.notificador.enviar_mensajes(
            f"{encabezado}\n{cuerpo}\n\n📅 *Fecha informe:* {fecha_string}"
        )

        if enviado:
            self._confirmar_transiciones(transiciones)
        else:
            logger.warning(
                "No se pudo notificar %s (%s): se reintenta en la proxima ejecucion",
                self.hostname,
                ", ".join(nombre for nombre, _accion, _mensaje in transiciones),
            )

    def lineas_telegraf(self) -> list[str]:
        """Una linea con los campos que tienen dato; ninguna si no hay datos."""
        campos = self._formatear_campos(CAMPOS_TELEGRAF)
        return [f"ups_temp2,host={self.hostname} {campos}"] if campos else []

    def ejecutar(self, oid_dicc: dict[str, str], oidtemp: str, oidtemp2: str) -> list[str]:
        """
        Devuelve las lineas de telegraf del UPS.
        - Un error al leer los datos se propaga: main lo registra y sigue con el resto de los UPS.
        - Un error al validar o notificar (base de datos, Google Chat) se registra aca y las
          metricas se devuelven igual, porque no dependen de la base ni del chat.
        """
        self.obtener_datos(oid_dicc, oidtemp, oidtemp2)
        lineas = self.lineas_telegraf()
        try:
            self.validar_datos_y_notificar()
        except Exception:
            logger.exception("Error al validar o notificar %s", self.hostname)
        return lineas
