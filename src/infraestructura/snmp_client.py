from easysnmp import Session, EasySNMPTimeoutError
import config.configuracion as c
import logging

class ClienteSNMP:
    def __init__(self,hostname):
        self.fullhostname = hostname + c.SUFIJO
        self.session = Session(hostname=self.fullhostname, community=c.COMMUNITY, version=c.VERSION_SNMP)
        self.logger = logging.getLogger(__name__)
    
    def obtener_valor(self,oid):
        try:
            valor_aux = self.session.get(oid).value
            return valor_aux
        except EasySNMPTimeoutError:
            self.logger.warning(f"Timeout SNMP en {self.fullhostname}",host=self.fullhostname, oid=oid)
            return None
        except Exception:
            self.logger.error(f"Error al obtener valor SNMP de {self.fullhostname} para OID {oid}",exc_info=False, host=self.fullhostname, oid=oid)
            return None