import pytest

from infraestructura.database import RepositorioDB
from infraestructura.snmp_client import ClienteSNMP


class ClienteSNMPFalso(ClienteSNMP):
    """
    Cliente SNMP sin red: responde con valores crudos (strings, como easysnmp) desde un diccionario.
    Un OID que no esta en el diccionario se comporta como timeout (None).
    Hereda obtener_valor_numerico para testear la conversion real.
    """

    def __init__(self, respuestas=None):
        self.respuestas = respuestas or {}

    def obtener_valor(self, oid):
        return self.respuestas.get(oid)


class NotificadorFalso:
    """
    Guarda los mensajes en lugar de enviarlos a Google Chat.
    Con falla=True simula un envio fallido: no guarda el mensaje y devuelve False.
    """

    def __init__(self):
        self.mensajes = []
        self.falla = False

    def enviar_mensajes(self, msg):
        if self.falla:
            return False
        self.mensajes.append(msg)
        return True


@pytest.fixture
def notificador():
    return NotificadorFalso()


@pytest.fixture
def repo_db(tmp_path):
    return RepositorioDB(str(tmp_path / "test_errores.db"))
