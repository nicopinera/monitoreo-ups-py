#!/usr/bin/python3

import config.configuracion as c
from config.logger import get_logger
from infraestructura.notificador import Notificador
from infraestructura.snmp_client import ClienteSNMP
from infraestructura.database import RepositorioDB
from drivers.state_ups import StateUPS
from drivers.dc_ups import DataCenterUPS
from drivers.hum_ups import HumedadUPS
from concurrent.futures import ThreadPoolExecutor

logger = get_logger(__name__)

def main():
    logger.info("Iniciando monitoreo UPS")
    
    # Creacion de clientes SNMP para host de state
    cliente_snmp_state = []
    for h in c.HOST_NAME_STATE:
        aux_client = ClienteSNMP(h)
        cliente_snmp_state.append(aux_client)
    
    # Creacion de cliente snmp del DC
    cliente_snmp_dc = ClienteSNMP(c.HOST_NAME_DC)
    
    # Creacion de cliente SNMP para humedad
    cliente_snmp_humedad = ClienteSNMP(c.HOST_NAME_HUMEDAD)
    
    # Notificador
    notificador = Notificador(c.ARCHIVO_ENV)
    
    # Repositorio de base de datos
    repo_db = RepositorioDB(c.ARCHIVO_DB)
    
    driver_state = []
    for host,client in zip(c.HOST_NAME_STATE,cliente_snmp_state):
        aux_drive_state = StateUPS(hostname=host,clienteSNMP=client,notificador=notificador,rep_db=repo_db)
        driver_state.append(aux_drive_state)
    
    dc_driver = DataCenterUPS(c.HOST_NAME_DC,clienteSNMP=cliente_snmp_dc)
    
    humedad_driver = HumedadUPS(hostname=c.HOST_NAME_HUMEDAD,clienteSNMP=cliente_snmp_humedad)
    
    humedad_driver.ejecutar(c.OID_HUMEDAD)
    dc_driver.ejecutar(c.OID_DC)
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        for d in driver_state:
            executor.submit(d.ejecutar,c.OID_UPS,c.OIDT,c.OIDTNEW)
            
if __name__== "__main__":
    try:
        main()
    except Exception:
        logger.exception("Error fatal en el flujo principal")
        raise
