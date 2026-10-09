#!/usr/bin/python3

from core.ups_base import BaseUPS
from core.errores import Errores
from core.validacion import (
    validar_carga,
    validar_load,
    validar_respuesta_snmp,
    validar_temp_bateria,
    validar_temp_uio,
    validar_tiempo_autonomia,
)
from datetime import datetime
import logging

# Orden de los campos en la linea de telegraf
CAMPOS_TELEGRAF = ("battery", "temp", "capacity", "load", "life", "current")

class StateUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
        self.logger = logging.getLogger(__name__)

    def obtener_datos(self, oid_dicc,oidtemp,oidtemp2):
        """Cada driver debe saber que OID pedir. Las metricas sin dato quedan en None."""
        self.datos = dict.fromkeys(CAMPOS_TELEGRAF)

        for nombre,oid in oid_dicc.items():
            valor = self.clienteSNMP.obtener_valor_numerico(oid)
            if valor is not None and nombre == 'life':
                valor = round(valor/6000,2)
            self.datos[nombre] = valor

        # Temperatura UIO: si el OID estandar no tiene dato se prueba el alternativo
        temp_val = self.clienteSNMP.obtener_valor_numerico(oidtemp)
        if temp_val is None:
            temp_val = self.clienteSNMP.obtener_valor_numerico(oidtemp2)
        self.datos["temp"] = int(temp_val) if temp_val is not None else None

    def _hay_datos(self):
        return any(valor is not None for valor in self.datos.values())
    
    def _gestionar_error_db(self, hay_error, msj_error, nombre_error_str, lista_mensajes):
        """
        Gestiona la lógica de persistencia y notificación:
        - Si hay error y no está activo -> Reactiva o Agrega y Notifica.
        - Si no hay error y está activo -> Resuelve y Notifica.
        """
        
        # Se busca un error activo
        error_db_activo = self.rep_db.error_activo(self.hostname, nombre_error_str)
        
        if hay_error: # El sensor reporta un problema
            if not error_db_activo: # No hay errores ACTIVOS
                # Si el error ya existía pero estaba resuelto, lo reactivamos
                if self.rep_db.error_resuelto(self.hostname, nombre_error_str): # hay error RESUELTO
                    self.rep_db.activar_error(self.hostname, nombre_error_str) # -> Se activa el error
                else: # No hay error RESUELTO tampoco
                    self.rep_db.agregar_error(self.hostname, nombre_error_str) # -> Se crea el evento
                
                lista_mensajes.append(f"❌ {msj_error}")
        else: # El sensor reporta que todo está normal
            if error_db_activo: # habia un error ACTIVO
                self.rep_db.resolver_error(self.hostname, nombre_error_str) # -> Se marca como resuelto
                lista_mensajes.append(f"✅ [RESUELTO] {nombre_error_str} volvió a la normalidad.")

    def _validar_metrica(self, nombre_metrica, funcion_validacion, error, lista_mensajes):
        """
        Valida una metrica y gestiona su error. Si la metrica no tiene dato no se hace nada:
        el error no se activa ni se resuelve, su estado en la DB queda como estaba.
        """
        valor = self.datos.get(nombre_metrica)
        if valor is None:
            return
        err, msg = funcion_validacion(valor)
        self._gestionar_error_db(err, msg, error.name, lista_mensajes)

    def validar_datos_y_notificar(self):
        """Valida los datos recolectados y gestiona las notificaciones agrupadas."""
        mensajes = []

        # Respuesta SNMP: si el equipo no devolvio ningun dato no se valida nada mas
        hay_datos = self._hay_datos()
        err, msg = validar_respuesta_snmp(hay_datos)
        self._gestionar_error_db(err, msg, Errores.SIN_RESPUESTA_SNMP.name, mensajes)

        if hay_datos:
            # Temperatura Baterías
            self._validar_metrica("battery", validar_temp_bateria, Errores.TEMPERATURA_BATERIA_ALTA, mensajes)

            # Sensor Temperatura Ambiente e I/O
            if self.datos.get("temp") is not None:
                err, msg = validar_temp_uio(self.datos["temp"])
                # Evaluamos ambos estados posibles para el sensor UIO
                self._gestionar_error_db(err if err == Errores.UIO_ROTO else None,
                                         msg if err == Errores.UIO_ROTO else None,
                                         Errores.UIO_ROTO.name, mensajes)
                self._gestionar_error_db(err if err == Errores.UIO_TEMPERATURA_ALTA else None,
                                         msg if err == Errores.UIO_TEMPERATURA_ALTA else None,
                                         Errores.UIO_TEMPERATURA_ALTA.name, mensajes)

            # Carga de las baterías
            self._validar_metrica("capacity", validar_carga, Errores.CARGA_MINIMA, mensajes)

            # Carga a la salida (Load)
            self._validar_metrica("load", validar_load, Errores.LOAD_MAXIMO, mensajes)

            # Tiempo de autonomía
            self._validar_metrica("life", validar_tiempo_autonomia, Errores.AUTONOMIA_MINIMO, mensajes)

        if mensajes:
            encabezado = f"🔔 *Reporte de Estado: {self.hostname}*\n"
            ahora = datetime.now()
            fecha_string = ahora.strftime("%d/%m/%Y %H:%M:%S")
            cuerpo = "\n".join(mensajes)
            self.notificador.enviar_mensajes(f"{encabezado}\n{cuerpo}\n\n📅 *Fecha informe:* {fecha_string}")

    def imprimir_telegraf(self):
        """Cada driver imprime su formato para grafana/telegraf. Los campos sin dato se omiten."""
        campos = self._formatear_campos(CAMPOS_TELEGRAF)
        if campos:
            print(f"ups_temp2,host={self.hostname} {campos}")
    
    def ejecutar(self,oid_dicc,oidtemp,oidtemp2):
        try:
            self.obtener_datos(oid_dicc,oidtemp,oidtemp2)
            self.imprimir_telegraf()
            self.validar_datos_y_notificar()
        except Exception as e:
            self.logger.exception(f"Error al ejecutar StateUPS para {self.hostname}",host=self.hostname,error=e)