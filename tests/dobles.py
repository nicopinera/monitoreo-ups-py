"""
Dobles de prueba (fakes) compartidos por los tests: reemplazan la red SNMP y Google Chat.
Viven aca y no en conftest.py porque conftest es para fixtures, no para importarlo.
Heredan de las clases reales para poder pasarlos donde el codigo espera esos tipos.
"""

from collections.abc import Mapping

from infraestructura.notificador import Notificador
from infraestructura.snmp_client import ClienteSNMP


class ClienteSNMPFalso(ClienteSNMP):
    """
    Cliente SNMP sin red: responde con valores crudos (strings, como easysnmp) desde un diccionario.
    Un OID que no esta en el diccionario se comporta como timeout (None).
    Hereda obtener_valor_numerico para testear la conversion real.
    """

    def __init__(self, respuestas: Mapping[str, str | None] | None = None) -> None:
        # No se llama al constructor real: crearia una sesion SNMP de verdad
        self.respuestas = respuestas or {}

    def obtener_valor(self, oid: str) -> str | None:
        return self.respuestas.get(oid)


class NotificadorFalso(Notificador):
    """
    Guarda los mensajes en lugar de enviarlos a Google Chat.
    Con falla=True simula un envio fallido: no guarda el mensaje y devuelve False.
    """

    def __init__(self) -> None:
        # No se llama al constructor real: leeria el .env
        self.mensajes: list[str] = []
        self.falla = False

    def enviar_mensajes(self, msg: str) -> bool:
        if self.falla:
            return False
        self.mensajes.append(msg)
        return True
