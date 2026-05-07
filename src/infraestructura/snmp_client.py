#!/usr/bin/python3

from easysnmp import Session, EasySNMPTimeoutError
import config.configuracion as c
from config.logger import get_logger

logger = get_logger(__name__)

class ClienteSNMP:
    def __init__(self,hostname):
        self.fullhostname = hostname + c.SUFIJO
        self.session = Session(hostname=self.fullhostname, community=c.COMMUNITY, version=c.VERSION_SNMP)
    
    def obtener_valor(self,oid):
        try:
            valor_aux = self.session.get(oid).value
            return valor_aux
        except EasySNMPTimeoutError:
            logger.warning("Timeout SNMP en %s OID %s", self.fullhostname, oid)
            return None
        except Exception:
            logger.error("Error al obtener valor SNMP de %s para OID %s", self.fullhostname, oid, exc_info=True)
            return None