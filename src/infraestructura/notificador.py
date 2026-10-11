#!/usr/bin/python3

import json
import logging
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

import config.configuracion as c


class Notificador:
    def __init__(self, ruta_env):
        load_dotenv(ruta_env)
        self.url = os.getenv(c.VAR_PASSWORDCHAT)
        self.logger = logging.getLogger(__name__)

    def enviar_mensajes(self, msg):
        """
        Envia el mensaje al webhook de Google Chat. Si falla, el error se registra y no se relanza.
        Usa urllib de la libreria estandar: para un POST con JSON no hace falta otra dependencia.
        """
        if not self.url:
            self.logger.error("URL de Google Chat no configurada (PASSWORDCHAT).")
            return
        # urlopen tambien abre file:// y otros esquemas: solo se acepta el webhook por https
        if not self.url.startswith("https://"):
            self.logger.error("La URL de Google Chat (PASSWORDCHAT) debe empezar con https://")
            return

        pedido = Request(
            self.url,
            data=json.dumps({"text": msg}).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        try:
            # Sin timeout, un Google Chat que no responde dejaria el hilo esperando para siempre
            with urlopen(pedido, timeout=c.HTTP_TIMEOUT):
                pass
        except HTTPError as e:
            # urlopen lanza HTTPError para las respuestas 4xx/5xx (por ejemplo 429 por limite de envio)
            self.logger.error(
                "Error al enviar mensaje a Google Chat: status=%s respuesta=%s",
                e.code,
                e.read().decode("utf-8", errors="replace"),
            )
        except Exception:
            self.logger.exception("Excepción al enviar mensaje a Google Chat")
