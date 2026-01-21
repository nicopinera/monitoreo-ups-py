from easysnmp import Session, EasySNMPTimeoutError
from Validar_datos import *

from httplib2 import Http
from json import dumps
import constantes as const
import sys, os

class UPS():
    hostname = '' # Nombre corto
    full_hostname = '' # Nombre completo para generar la sesion SNMP
    url = ''
    session = None # Objeto Sesion
    temperatura_bateria = 0 # Temperatura Baterias
    temperatura_uio1 = 0 # Temperatura del sensor UIO
    carga = 0 # Porcentaje de Carga
    load = 0 # Carga a la salida
    tiempo_autonomia = 0 # Tiempo de autonomia 
    corriente = 0 # Corriente suministrada por el UPS

    def __init__(self,hostname,url):
        self.hostname = hostname
        self.full_hostname = hostname+'.psi.unc.edu.ar' # Se genera el nombre de Host completo
        self.url = url
        self.session = Session(hostname=self.full_hostname, community=const.COMMUNITY, version=1) # Sesion SNMP
        self.obtener_datos()
        self.toString()
        #self.validar_datos()
    
    def obtener_datos(self):
        try:
            self.temperatura_bateria = int(self.session.get(const.OIDB).value)/1
            self.carga = float(self.session.get(const.OIDCAPACITY).value)
            self.load = float(self.session.get(const.OIDLOAD).value)
            tiempo_aux = round((int(self.session.get(const.OIDLIFE).value))/6000,2) # Calculo para obtener minutos
            self.tiempo_autonomia = tiempo_aux
            self.corriente = float(self.session.get(const.OIDCURRENT).value)
            try:
                self.temperatura_uio1 = float(self.session.get(const.OIDT).value)
            except:
                self.temperatura_uio1 = float(self.session.get(const.OIDTNEW).value)   
        except EasySNMPTimeoutError as error:  
            print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
            sys.exit(0)
        except Exception as error2:
            print(f"Ocurrió un error inesperado: {error2}. El programa terminará. ")
            sys.exit(0)
    
    def validar_datos(self):
        mensajes = []
        val, msg = validar_temp_bateria(self.temperatura_bateria, self.hostname)
        if not val and msg:
            mensajes.append(msg)

        val, msg = validar_temp_uio(self.temperatura_uio1, self.hostname)
        if not val and msg:
            mensajes.append(msg)

        val, msg = validar_carga(self.carga, self.hostname)
        if not val and msg:
            mensajes.append(msg)

        val, msg = validar_load(self.load, self.hostname)
        if not val and msg:
            mensajes.append(msg)

        val, msg = validar_tiempo_autonomia(self.tiempo_autonomia, self.hostname)
        if not val and msg:
            mensajes.append(msg)

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