"""
Dobles de prueba (fakes) compartidos por los tests: reemplazan la red SNMP y Google Chat.
Viven aca y no en conftest.py porque conftest es para fixtures, no para importarlo.
Heredan de las clases reales para poder pasarlos donde el codigo espera esos tipos.
"""

import logging
from collections.abc import Mapping
from typing import Any

from config.entorno import AjustesSNMP, Entorno
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


def entorno_de_prueba(data_dir: str, **cambios: Any) -> Entorno:
    """Entorno valido para tests, sin webhook real (nunca manda mensajes a Google Chat)."""
    valores: dict[str, Any] = {
        "webhook_url": None,
        "snmp": AjustesSNMP(community="comunidad-de-prueba", timeout=1.0, retries=1),
        "http_timeout": 10.0,
        "max_workers": 4,
        "log_level": logging.INFO,
        "data_dir": data_dir,
    }
    valores.update(cambios)
    return Entorno(**valores)
