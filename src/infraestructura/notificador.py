#!/usr/bin/python3

from dotenv import load_dotenv
import os, time,logging
import config.configuracion as c
from httplib2 import Http
from json import dumps

class Notificador:
    def __init__(self,ruta_env):
        load_dotenv(ruta_env)
        self.url = os.getenv(c.VAR_PASSWORDCHAT)
        self.logger = logging.getLogger(__name__)
    
    def enviar_mensajes(self,msg):
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
                body=dumps(app_message).encode('utf-8')
            )
            
            if response.status != 200:
                self.logger.error("Error al enviar mensaje a Google Chat", status=response.status, contenido=content.decode('utf-8'))
        except Exception:
            self.logger.error("Excepción al enviar mensaje a Google Chat", exc_info=True)