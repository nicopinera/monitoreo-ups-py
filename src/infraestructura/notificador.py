import json
import logging
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from core.alertas import Evento
from infraestructura.formato_chat import armar_mensaje, clave_hilo


def url_con_hilo(url: str, clave: str) -> str:
    """
    Agrega al webhook el hilo del mensaje. threadKey agrupa los mensajes con la misma clave y
    REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD crea el hilo si todavia no existe. La URL del webhook
    ya trae parametros (key, token): se suman sin pisarlos.
    """
    partes = urlsplit(url)
    parametros = parse_qsl(partes.query, keep_blank_values=True)
    parametros += [
        ("threadKey", clave),
        ("messageReplyOption", "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"),
    ]
    return urlunsplit(partes._replace(query=urlencode(parametros)))


class Notificador:
    def __init__(self, url: str | None, timeout: float, grafana_url: str | None = None) -> None:
        """
        url: webhook de Google Chat (GOOGLE_CHAT_WEBHOOK_URL). timeout: segundos por envio.
        grafana_url: destino del boton "Ver en Grafana" (sin boton si es None).
        """
        self.url = url
        self.timeout = timeout
        self.grafana_url = grafana_url
        self.logger = logging.getLogger(__name__)

    def notificar(self, evento: Evento) -> bool:
        """Avisa un evento como tarjeta, en el hilo de su incidente."""
        return self.enviar(armar_mensaje(evento, self.grafana_url), clave_hilo(evento))

    def enviar(self, mensaje: dict[str, Any], hilo: str | None = None) -> bool:
        """
        Envia el mensaje al webhook de Google Chat. Devuelve True si Google Chat lo acepto y
        False si no se pudo enviar (el motivo queda en el log, la excepcion no se relanza).
        Usa urllib de la libreria estandar: para un POST con JSON no hace falta otra dependencia.
        """
        if not self.url:
            self.logger.error("URL de Google Chat no configurada (GOOGLE_CHAT_WEBHOOK_URL)")
            return False
        # urlopen tambien abre file:// y otros esquemas: solo se acepta el webhook por https.
        # cargar_entorno ya lo valida; se repite aca por si el Notificador se crea de otra forma
        if not self.url.startswith("https://"):
            self.logger.error("La URL de Google Chat debe empezar con https://")
            return False

        pedido = Request(  # noqa: S310 (esquema validado arriba)
            url_con_hilo(self.url, hilo) if hilo else self.url,
            data=json.dumps(mensaje).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        try:
            # Sin timeout, un Google Chat que no responde dejaria el hilo esperando para siempre.
            # S310: el esquema ya se valido arriba (solo https)
            with urlopen(pedido, timeout=self.timeout):  # noqa: S310
                return True
        except HTTPError as e:
            # urlopen lanza HTTPError para las respuestas 4xx/5xx (por ejemplo 429 por limite, o
            # 400 si la tarjeta tiene un campo que Chat no acepta)
            self.logger.error(
                "Error al enviar mensaje a Google Chat: status=%s respuesta=%s",
                e.code,
                e.read().decode("utf-8", errors="replace"),
            )
        except Exception:
            self.logger.exception("Excepción al enviar mensaje a Google Chat")
        return False
