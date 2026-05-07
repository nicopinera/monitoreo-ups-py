#!/usr/bin/python3

from config.logger import get_logger, get_telegraf_logger
from core.ups_base import BaseUPS
from core.validacion import *

logger = get_logger(__name__)
telegraf_logger = get_telegraf_logger()

class StateUPS(BaseUPS):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        super().__init__(hostname, clienteSNMP, notificador, rep_db)
    
    def obtener_datos(self, oid_dicc,oidtemp,oidtemp2):
        """Cada driver debe saber que OID pedir"""
        # Temperatura bateria
        
        self.datos = {
            "battery": 0,
            "temp": 0,
            "capacity": 0,
            "load": 0,
            "life": 0,
            "current": 0
        }
        
        for nombre,oid in oid_dicc.items():
            dato_aux = self.clienteSNMP.obtener_valor(oid)
            if dato_aux is not None:
                try:
                    if nombre == 'life':
                        self.datos[nombre] = round((int(dato_aux))/6000,2)
                    else:
                        self.datos[nombre] = dato_aux
                except (TypeError,ValueError) as e:
                    self.datos[nombre] = 0
        
        temp_val = self.clienteSNMP.obtener_valor(oidtemp)
        if temp_val is None:
            temp_val = self.clienteSNMP.obtener_valor(oidtemp2)
        self.datos["temp"] = int(temp_val) if temp_val is not None else 0
    
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
                self.rep_db.resolver_error(self.hostname, nombre_error_str) # -> Se marca como activo
                lista_mensajes.append(f"✅ [RESUELTO] {nombre_error_str} volvió a la normalidad.") # Se marca resuelto
    
    def validar_datos_y_notificar(self):
        """Valida los datos recolectados y gestiona las notificaciones agrupadas."""
        mensajes = [] 
        
        # Temperatura Baterías
        err, msg = validar_temp_bateria(self.datos.get("battery", 0))
        self._gestionar_error_db(err, msg, "TEMPERATURA_BATERIA_ALTA", mensajes)
        
        # Sensor Temperatura Ambiente e I/O
        err, msg = validar_temp_uio(self.datos.get("temp", 0))
        # Evaluamos ambos estados posibles para el sensor UIO
        self._gestionar_error_db(err if err == Errores.UIO_ROTO else None, 
                                 msg if err == Errores.UIO_ROTO else None, 
                                 "UIO_ROTO", mensajes)
        self._gestionar_error_db(err if err == Errores.UIO_TEMPERATURA_ALTA else None, 
                                 msg if err == Errores.UIO_TEMPERATURA_ALTA else None, 
                                 "UIO_TEMPERATURA_ALTA", mensajes)
        
        # Carga de las baterías
        err, msg = validar_carga(self.datos.get("capacity", 0))
        self._gestionar_error_db(err, msg, "CARGA_MINIMA", mensajes)
        
        # Carga a la salida (Load)
        err, msg = validar_load(self.datos.get("load", 0))
        self._gestionar_error_db(err, msg, "LOAD_MAXIMO", mensajes)
        
        # Tiempo de autonomía 
        err, msg = validar_tiempo_autonomia(self.datos.get("life", 0))
        self._gestionar_error_db(err, msg, "AUTONOMIA_MINIMO", mensajes)
        
        if mensajes:
            encabezado = f"🔔 *Reporte de Estado: {self.hostname}*\n"
            cuerpo = "\n".join(mensajes)
            self.notificador.enviar_mensajes(f"{encabezado}\n{cuerpo}")

    def imprimir_telegraf(self):
        """Cada driver imprime su formato para grafana/telegraf"""
        print(f"ups_temp2,host={self.hostname} battery={self.datos['battery']},temp={self.datos['temp']},capacity={self.datos['capacity']},load={self.datos['load']},life={self.datos['life']},current={self.datos['current']}")
    
    def ejecutar(self,oid_dicc,oidtemp,oidtemp2):
        try:
            self.obtener_datos(oid_dicc,oidtemp,oidtemp2)
            self.imprimir_telegraf()
            self.validar_datos_y_notificar()
        except Exception:
            logger.exception("Error al ejecutar StateUPS para %s", self.hostname)