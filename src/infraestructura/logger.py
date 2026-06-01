#!/usr/bin/python3

import logging
from logging.handlers import RotatingFileHandler
import seqlog
import config.configuracion as c


def configurar_logger(server_url="http://localhost:5341", api_key=None):
    """
    Configura el logger global para enviar datos a Seq.
    server_url: La dirección de tu VM donde corre el contenedor de Seq.
    """
    # 1. Configurar seqlog
    # Las propiedades globales aparecerán en todos los logs de este script
    seqlog.set_global_log_properties(
        Application="UPS-Monitor-System",
        Environment="Produccion"
    )
    
    # 2. Establecer la conexión con el servidor Seq
    seqlog.log_to_seq(
        server_url="http://localhost:5341",
        level=logging.DEBUG,
        batch_size=1,
        auto_flush_timeout=1,
        override_root_logger=True
    )

    # 3. Nivel de log por defecto
    logging.getLogger().setLevel(logging.INFO)

