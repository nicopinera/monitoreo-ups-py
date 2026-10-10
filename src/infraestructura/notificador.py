#!/usr/bin/python3

import logging
import os
import time
from json import dumps

from dotenv import load_dotenv
from httplib2 import Http

import config.configuracion as c


class Notificador:
    def __init__(self, ruta_env):
        load_dotenv(ruta_env)
        self.url = os.getenv(c.VAR_PASSWORDCHAT)
        self.logger = logging.getLogger(__name__)

    def enviar_mensajes(self, msg):
        if not self.url:
            self.logger.error("URL de Google Chat no configurada (PASSWORDCHAT).")
            return

        message_headers = {"Content-Type": "application/json; charset=UTF-8"}
        app_message = {"text": msg}

        try:
            time.sleep(1)
            # httplib2.Http() no es thread-safe, se crea uno nuevo por petición o se usa un lock
            http_obj = Http()
            response, content = http_obj.request(
                uri=self.url,
                method="POST",
                headers=message_headers,
                body=dumps(app_message).encode("utf-8"),
            )

            if response.status != 200:
                self.logger.error(
                    "Error al enviar mensaje a Google Chat: status=%s respuesta=%s",
                    response.status,
                    content.decode("utf-8", errors="replace"),
                )
        except Exception:
            self.logger.exception("Excepción al enviar mensaje a Google Chat")
