import logging
import math

from easysnmp import EasySNMPTimeoutError, Session

import config.configuracion as c

# Valor numerico de un OID; None si no hubo respuesta o no es un numero valido
Numero = int | float


class ClienteSNMP:
    """
    Cliente SNMP de un host. Se crea uno por host y por ejecucion.
    Despues del primer timeout no se consultan mas OIDs de ese host en esta ejecucion:
    si no respondio a uno, esperar el timeout de cada OID restante solo alarga la ejecucion.
    """

    def __init__(self, hostname: str) -> None:
        self.fullhostname = hostname + c.SUFIJO
        self.session = Session(
            hostname=self.fullhostname,
            community=c.COMMUNITY,
            version=c.VERSION_SNMP,
            timeout=c.SNMP_TIMEOUT,
            retries=c.SNMP_RETRIES,
        )
        self.logger = logging.getLogger(__name__)
        self.sin_respuesta = False

    def obtener_valor(self, oid: str) -> str | None:
        if self.sin_respuesta:
            return None
        try:
            valor: str = self.session.get(oid).value
            return valor
        except EasySNMPTimeoutError:
            self.sin_respuesta = True
            self.logger.warning(
                "Timeout SNMP en %s (oid=%s), no se consultan mas OIDs de este host",
                self.fullhostname,
                oid,
            )
            return None
        except Exception as e:
            self.logger.error(
                "Error al obtener valor SNMP de %s (oid=%s): %s", self.fullhostname, oid, e
            )
            return None

    def obtener_valor_numerico(self, oid: str) -> Numero | None:
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
