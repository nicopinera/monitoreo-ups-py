#!/usr/bin/python3    

import constantes as const
from easysnmp import Session, EasySNMPTimeoutError
import sys

# Funcion principal
def main():
    sesion_ups = Session(hostname=const.HOST_NAME, community='publicapc', version=2, timeout=5,retries=1)
    try:
        aux = sesion_ups.get(const.OIDB)
        bateria = aux.value
        print(f"Temperatura de las baterias: {bateria} °C")
        try:
            aux = sesion_ups.get(const.OIDT)
            temperatura_uio = aux.value
            print(f"Temperatura del sensor: {temperatura_uio} °C")
        except:
            aux = sesion_ups.get(const.OIDTNEW)
            temperatura_uio = aux.value
            print(f"Temperatura del sensor: {temperatura_uio} °C")
        aux = sesion_ups.get(const.OIDCapacity)
        capacidad_bateria = aux.value
        print(f"Capacidad de la bateria: {capacidad_bateria} %")
        aux = sesion_ups.get(const.OIDLOAD)
        carga_salida = aux.value
        print(f"Carga a la salida: {carga_salida} %")
        aux = sesion_ups.get(const.OIDLife)
        tiempo_autonomia = aux.value
        tiempo_autonomia = (int(tiempo_autonomia))/6000
        print(f"Tiempo de autonomia: {tiempo_autonomia} minutos")
        aux = sesion_ups.get(const.OIDCurrent)
        corriente = aux.value
        print(f"Corriente: {corriente} A")
    except EasySNMPTimeoutError as error:
        # easysnmp.exceptions.EasySNMPTimeoutError: Excepcion de tiempo de espera al conectar con el host remoto.   
        print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
        sys.exit(0)
    except Exception as error2:
        print(f"Ocurrió un error inesperado: {error2}. El programa terminará. ")
        sys.exit(0)

if __name__ == "__main__":
    main()