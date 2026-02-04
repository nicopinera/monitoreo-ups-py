#!/usr/bin/python3 

import constantes as const
from easysnmp import Session, EasySNMPTimeoutError
import sys

def obtener_datos(sesion_snmp):
    oid = {
        "autonomia": const.OID_AUTONOMIA,
        "carga_bat":const.OID_CARGA_BATERIA,
        "bat_temp":const.OID_TEMP_BATERIA
    }
    datos = {}
    for nombre,oid in oid.items():
        aux = sesion_snmp.get(oid)
        if nombre == "autonomia":
            datos[nombre] = round(int(aux.value)/60,2)
        else:
            datos[nombre] = aux.value
    return datos

# Funcion principal
def main():
    sesion_ups = Session(hostname=const.HOST_NAME, community=const.COMMUNITY, version=1)
    try:
        datos = obtener_datos(sesion_ups)
        ups = const.HOST_NAME.split(".")[0]
        print(f"dc-ups,host={ups} autonomia={datos['autonomia']},carga_bat={datos['carga_bat']},bat_temp={datos['bat_temp']}")
    except EasySNMPTimeoutError as error:
        # easysnmp.exceptions.EasySNMPTimeoutError: Excepcion de tiempo de espera al conectar con el host remoto.   
        print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
        sys.exit(0)
    except Exception as error2:
        print(f"Ocurrió un error inesperado: {error2}. El programa terminará. ")
        sys.exit(0)

if __name__ == "__main__":
    main()