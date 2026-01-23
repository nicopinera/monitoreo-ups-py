from easysnmp import Session, EasySNMPTimeoutError
from Validar_datos import *
from Base_Datos import BaseDatos
from httplib2 import Http
from json import dumps
import constantes as const
import sys, os

class UPS():
    """
    Docstring for UPS
    Temperatura_baterias = Almacena la temperatura actual de las baterias
    Temperatura_uio1 = Almacena la temperatura actual medida por el sensor de temperatura
    Carga = Representa el % de carga de las baterias
    Load = Representa el % de carga conectada al UPS
    tiempo_autonomia = Representa el tiempo de autonomia en min del UPS
    corriente = Representa la corriente suministrada por el UPS a los dispositivos conectados
    """
    temperatura_bateria, temperatura_uio1,carga,load,tiempo_autonomia,corriente = 0,0,0,0,0,0

    def __init__(self,hostname,url,db_file):
        self.hostname = hostname # Nombre corto
        self.full_hostname = hostname+'.psi.unc.edu.ar' # Nombre completo para generar la sesion SNMP
        self.url = url # URL del webhook para notificaciones
        self.db = BaseDatos(db_file)
        self.db.Crear_Base_datos()
        self.session = Session(hostname=self.full_hostname, community=const.COMMUNITY, version=1) # Sesion SNMP
        self.obtener_datos()
        self.toString()
    
    def obtener_datos(self):
        try:
            self.temperatura_bateria = self.session.get(const.OIDB).value
            self.carga = self.session.get(const.OIDCAPACITY).value
            self.load = self.session.get(const.OIDLOAD).value
            tiempo_aux = round((int(self.session.get(const.OIDLIFE).value))/6000,2) # Calculo para obtener minutos
            self.tiempo_autonomia = tiempo_aux
            self.corriente = self.session.get(const.OIDCURRENT).value
            try:
                self.temperatura_uio1 = self.session.get(const.OIDT).value
            except:
                self.temperatura_uio1 = self.session.get(const.OIDTNEW).value   
        except EasySNMPTimeoutError as error:  
            print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
            sys.exit(0)
        except Exception as error2:
            print(f"Ocurrió un error inesperado: {error2}. El programa terminará. ")
            sys.exit(0)
    
    def validar_datos(self):
        mensajes = []

        # Validacion de temperatura de baterias
        error, msg = validar_temp_bateria(self.temperatura_bateria, self.hostname)
        if error is not None:
            if self.db.error_activo(self.hostname, error.name) is None:
                self.db.agregar_error(self.hostname, error.name)
                mensajes.append(msg)
        else:
            if self.db.error_activo(self.hostname, "TEMPERATURA_BATERIA_ALTA") is not None:
                self.db.resolver_error(self.hostname, "TEMPERATURA_BATERIA_ALTA")
                mensajes.append(f"[RESUELTO - {self.hostname}] TEMPERATURA BATERIAS volvio a la normalidad")

        # Validacion de temperatura UIO
        error, msg = validar_temp_uio(self.temperatura_uio1, self.hostname)
        if error is not None:
            if self.db.error_activo(self.hostname, error.name) is None:
                self.db.agregar_error(self.hostname, error.name)
                mensajes.append(msg)
        else:
            uio_roto = self.db.error_activo(self.hostname, "UIO_ROTO")
            uio_temp = self.db.error_activo(self.hostname, "UIO_TEMPERATURA_ALTA")
            if uio_roto is not None or uio_temp is not None:
                self.db.resolver_error(self.hostname, "UIO_ROTO")
                self.db.resolver_error(self.hostname, "UIO_TEMPERATURA_ALTA")
                mensajes.append(f"[RESUELTO - {self.hostname}] TEMPERATURA AMBIENTE volvio a la normalidad")

        # Validacion de carga
        error, msg = validar_carga(self.carga, self.hostname)
        if error is not None:
            if self.db.error_activo(self.hostname, error.name) is None:
                self.db.agregar_error(self.hostname, error.name)
                mensajes.append(msg)
        else:
            if self.db.error_activo(self.hostname, "CARGA_MINIMA") is not None:
                self.db.resolver_error(self.hostname, "CARGA_MINIMA")
                mensajes.append(f"[RESUELTO - {self.hostname}] La CARGA volvio a la normalidad")

        # Validacion de load
        error, msg = validar_load(self.load, self.hostname)
        if error is not None:
            if self.db.error_activo(self.hostname, error.name) is None:
                self.db.agregar_error(self.hostname, error.name)
                mensajes.append(msg)
        else:
            if self.db.error_activo(self.hostname, "LOAD_MAXIMO") is not None:
                self.db.resolver_error(self.hostname, "LOAD_MAXIMO")
                mensajes.append(f"[RESUELTO - {self.hostname}] LOAD volvio a la normalidad")

        # Validacion de tiempo de autonomia
        error, msg = validar_tiempo_autonomia(self.tiempo_autonomia, self.hostname)
        if error is not None:
            if self.db.error_activo(self.hostname, error.name) is None:
                self.db.agregar_error(self.hostname, error.name)
                mensajes.append(msg)
        else:
            if self.db.error_activo(self.hostname, "AUTONOMIA_MINIMO") is not None:
                self.db.resolver_error(self.hostname, "AUTONOMIA_MINIMO")
                mensajes.append(f"[RESUELTO - {self.hostname}] TIEMPO AUTONOMIA volvio a la normalidad")

        # Siempre imprimir datos para Grafana
        self.toString()

        if mensajes:
            mensaje_final = "\n".join(mensajes)
            self.envio_mensaje(mensaje_final)

    def envio_mensaje(self,msg):
        message_headers = {"Content-Type": "application/json; charset=UTF-8"}
        http_obj = Http()
        app_message = {"text": msg}
        http_obj.request(uri=self.url, method="POST", headers=message_headers, body=dumps(app_message), )

    def toString(self): # Texto en formato para Grafana
        print(f"ups_temp2,host={self.hostname} battery={self.temperatura_bateria},temp={self.temperatura_uio1},capacity={self.carga},load={self.load},life={self.tiempo_autonomia},current={self.corriente}")