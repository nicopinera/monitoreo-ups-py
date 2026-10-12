import json
import logging
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class Notificador:
    def __init__(self, url: str | None, timeout: float) -> None:
        """url: webhook de Google Chat (GOOGLE_CHAT_WEBHOOK_URL). timeout: segundos por envio."""
        self.url = url
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    def enviar_mensajes(self, msg: str) -> bool:
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
            self.url,
            data=json.dumps({"text": msg}).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        try:
            # Sin timeout, un Google Chat que no responde dejaria el hilo esperando para siempre.
            # S310: el esquema ya se valido arriba (solo https)
            with urlopen(pedido, timeout=self.timeout):  # noqa: S310
                return True
        except HTTPError as e:
            # urlopen lanza HTTPError para las respuestas 4xx/5xx (por ejemplo 429 por limite)
            self.logger.error(
                "Error al enviar mensaje a Google Chat: status=%s respuesta=%s",
                e.code,
                e.read().decode("utf-8", errors="replace"),
            )
        except Exception:
            self.logger.exception("Excepción al enviar mensaje a Google Chat")
        return False
