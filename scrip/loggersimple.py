import logging

# Crear un logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
#Define el "filtro de entrada". Solo los mensajes con nivel DEBUG o superior entrarán al logger.

# Crear un handler (archivo)
handler = logging.FileHandler('app.log')
handler.setLevel(logging.INFO)

# Crear un formatter (formato del mensaje)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Agregar el handler al logger
logger.addHandler(handler)

# Usar
logger.info("La aplicación inició correctamente")
logger.error("Ocurrió un error grave")