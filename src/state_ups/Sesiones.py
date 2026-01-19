from easysnmp import Session, EasySNMPTimeoutError
import constantes as const
import sys

class UPS():
    hostname = '' # Nombre corto
    full_hostname = '' # Nombre completo para generar la sesion SNMP
    session = None # Objeto Sesion
    temperatura_bateria = 0 # Temperatura Baterias
    temperatura_uio1 = 0 # Temperatura del sensor UIO
    carga = 0 # Porcentaje de Carga
    load = 0 # Carga a la salida
    tiempo_autonomia = 0 # Tiempo de autonomia 
    corriente = 0 # Corriente suministrada por el UPS

    def __init__(self,hostname):
        self.hostname = hostname
        self.full_hostname = hostname+'.psi.unc.edu.ar' # Se genera el nombre de Host completo
        self.session = Session(hostname=self.full_hostname, community=const.COMMUNITY, version=1) # Sesion SNMP
        self.obtener_datos()
    
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
    
    def toString(self): # Texto en formato para Grafana
        print(f"ups_temp2,host={self.hostname} battery={self.temperatura_bateria},temp={self.temperatura_uio1},capacity={self.carga},load={self.load},life={self.tiempo_autonomia},current={self.corriente}")