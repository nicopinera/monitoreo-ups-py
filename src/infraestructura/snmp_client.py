from easysnmp import Session, EasySNMPTimeoutError
import config.configuracion as c
import logging
import math

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

    def obtener_valor_numerico(self,oid):
        """
        Devuelve el valor del OID como int (o float si tiene decimales).
        Devuelve None si no hubo respuesta o si el valor no es numerico,
        por ejemplo NOSUCHOBJECT / NOSUCHINSTANCE o vacio.
        """
        valor = self.obtener_valor(oid)
        if valor is None:
            return None
        try:
            return int(valor)
        except (TypeError, ValueError):
            pass
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return None
        # nan / inf no son validos en line protocol
        return numero if math.isfinite(numero) else None