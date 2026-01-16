from easysnmp import Session, EasySNMPTimeoutError
import constantes as const
import sys

class UPS():
    hostname = ''
    full_hostname = ''
    session = None
    temperatura_bateria = 0
    temperatura_uio1 = 0
    carga = 0
    load = 0
    tiempo_autonomia = 0
    corriente = 0

    def __init__(self,hostname):
        self.hostname = hostname.split('.')[0]
        self.full_hostname = hostname
        self.session = Session(hostname=self.full_hostname, community=const.COMMUNITY, version=1)
        self.obtener_datos()
    
    def obtener_datos(self):
        try:
            self.temperatura_bateria = self.session.get(const.OIDB).value
            self.carga = self.session.get(const.OIDCapacity).value
            self.load = self.session.get(const.OIDLOAD).value
            tiempo_aux = round((int(self.session.get(const.OIDLife).value))/6000,2)
            self.tiempo_autonomia = tiempo_aux
            self.corriente = self.session.get(const.OIDCurrent).value
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
    
    def toString(self):
        print(f"ups_temp,host={self.hostname} battery={self.temperatura_bateria},temp={self.temperatura_uio1},capacity={self.carga},load={self.load},life={self.tiempo_autonomia},current={self.corriente}")