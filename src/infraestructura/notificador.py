from dotenv import load_dotenv
import os, time
import config.configuracion as c
from config.logger import get_logger
from httplib2 import Http
from json import dumps

logger = get_logger(__name__)

class Notificador:
    def __init__(self,ruta_env):
        load_dotenv(ruta_env)
        self.url = os.getenv(c.VAR_PASSWORDCHAT)
    
    def enviar_mensajes(self,msg):
        if not self.url:
            logger.error("URL de Google Chat no configurada (PASSWORDCHAT).")
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
                logger.error("Error al enviar mensaje a Google Chat: %s - %s", response.status, content.decode('utf-8'))
        except Exception:
            logger.error("Excepción al enviar mensaje a Google Chat", exc_info=True)
