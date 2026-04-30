from dotenv import load_dotenv
import os
import config.configuracion as c
from httplib2 import Http
from json import dumps

class Notificador:
    def __init__(self,ruta_env):
        load_dotenv(ruta_env)
        self.url = os.getenv(c.VAR_PASSWORDCHAT)
        self.http_obj = Http()
    
    def enviar_mensajes(self,msg):
        message_headers = {"Content-Type": "application/json; charset=UTF-8"}
        app_message = {"text": msg}
        self.http_obj.request(uri=self.url, method="POST", headers=message_headers, body=dumps(app_message))