import src.config.configuracion as c
from src.core.notificador import Notificador

def test_notificador():
    print(f"Probando notificador con archivo: {c.ARCHIVO_ENV}")
    notificador = Notificador(c.ARCHIVO_ENV)
    print(f"URL cargada: {notificador.url[:20]}...{notificador.url[-10:] if notificador.url else 'None'}")
    
    if notificador.url:
        notificador.enviar_mensajes("🧪 *Prueba de Notificación*\nEl sistema de monitoreo ha sido actualizado y esta es una prueba de conectividad.")
        print("Mensaje enviado. Revisa tu Google Chat.")
    else:
        print("Error: No se pudo cargar la URL del .env")

if __name__ == "__main__":
    test_notificador()
