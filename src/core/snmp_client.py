from easysnmp import Session, EasySNMPTimeoutError
import config.configuracion as c

class ClienteSNMP:
    def __init__(self,hostname):
        self.fullhostname = hostname + c.SUFIJO
        self.session = Session(hostname=self.fullhostname, community=c.COMMUNITY, version=c.VERSION_SNMP)
    
    def obtener_valor(self,oid):
        try:
            valor_aux = self.session.get(oid).value
            return valor_aux
        except (EasySNMPTimeoutError,Exception) as error:  
            # print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
            return None