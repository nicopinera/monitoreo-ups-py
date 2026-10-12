import logging
import math

from ezsnmp import Session
from ezsnmp import exceptions as errores_snmp

import config.configuracion as c
from config.entorno import AjustesSNMP

# Valor numerico de un OID; None si no hubo respuesta o no es un numero valido
Numero = int | float

# Tipos que devuelve ezsnmp (SNMPv2c) cuando el OID no existe en el equipo
TIPOS_SIN_DATO = ("NOSUCHOBJECT", "NOSUCHINSTANCE", "ENDOFMIBVIEW")


class ClienteSNMP:
    """
    Cliente SNMP de un host (con ezsnmp). Se crea uno por host y por ejecucion.
    Si el host no responde (timeout) o no se puede contactar (por ejemplo, el nombre no resuelve
    DNS), no se consultan mas OIDs de ese host en esta ejecucion: esperar cada OID restante solo
    alargaria la ejecucion.
    """

    def __init__(self, hostname: str, ajustes: AjustesSNMP) -> None:
        self.fullhostname = hostname + c.SUFIJO
        self.session = Session(
            hostname=self.fullhostname,
            community=ajustes.community,
            version=c.VERSION_SNMP,
            timeout=ajustes.timeout,
            retries=ajustes.retries,
        )
        self.logger = logging.getLogger(__name__)
        self.sin_respuesta = False

    def obtener_valor(self, oid: str) -> str | None:
        if self.sin_respuesta:
            return None
        try:
            resultado = self.session.get(oid)[0]  # ezsnmp devuelve una tupla de resultados
        except (errores_snmp.TimeoutError, errores_snmp.ConnectionError) as e:
            self.sin_respuesta = True
            self.logger.warning(
                "Sin respuesta SNMP de %s (oid=%s): %s. No se consultan mas OIDs de este host",
                self.fullhostname,
                oid,
                _primera_linea(e),
            )
            return None
        except Exception as e:
            if _es_oid_inexistente(e):
                self.logger.debug("OID inexistente en %s (oid=%s)", self.fullhostname, oid)
            else:
                self.logger.error(
                    "Error SNMP de %s (oid=%s): %s", self.fullhostname, oid, _primera_linea(e)
                )
            return None

        if resultado.type in TIPOS_SIN_DATO:
            return None
        valor: str = resultado.value
        return valor

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


def _primera_linea(error: Exception) -> str:
    """Los mensajes de ezsnmp traen varias lineas y saltos de linea al final."""
    return str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__


def _es_oid_inexistente(error: Exception) -> bool:
    """
    El equipo respondio, pero no tiene ese OID: es "sin dato", no un error (por ejemplo OIDT en
    firmware nuevo, que usa OIDTNEW). Con SNMPv1, ezsnmp lo informa como PacketError
    "(noSuchName)" (verificado contra el UPS del DC).
    """
    if isinstance(error, errores_snmp.PacketError):
        return "noSuchName" in str(error)
    return isinstance(
        error,
        errores_snmp.NoSuchObjectError
        | errores_snmp.NoSuchInstanceError
        | errores_snmp.NoSuchNameError,
    )
