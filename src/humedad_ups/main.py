#!/usr/bin/python3 

import constantes as const
from easysnmp import Session, EasySNMPTimeoutError
import sys

# Funcion principal
def main():
    sesion_ups = Session(hostname=const.HOST_NAME, community=const.COMMUNITY, version=2)
    try:
        aux = sesion_ups.get(const.ODIH2)
        humedad = aux.value
        print(f"Humedad UPS: {humedad}%")
    except EasySNMPTimeoutError as error:
        # easysnmp.exceptions.EasySNMPTimeoutError: Excepcion de tiempo de espera al conectar con el host remoto.   
        print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
        sys.exit(0)
    except Exception as error2:
        print(f"Ocurrió un error inesperado: {error2}. El programa terminará. ")
        sys.exit(0)

if __name__ == "__main__":
    main()