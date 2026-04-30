import config.configuracion as c
from core.notificador import Notificador
from core.snmp_client import ClienteSNMP
from core.database import RepositorioDB

def main():
    
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
    
    print("Hola mundo")

if __name__== "__main__":
    main()