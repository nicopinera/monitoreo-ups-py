#!/usr/bin/python3    

import constantes as const
from easysnmp import Session, EasySNMPTimeoutError
import sys

temp_bateria = []
temp_uio = []
capacidad_bateria = []
carga_salida = []
tiempo_autonomia = []
corriente = []
sesiones = []

def obtener_hostname(nombre):
    return nombre.split('.')[0]

def print_info(temp_bateria, temperatura_uio, capacidad_bateria, carga_salida, tiempo_autonomia, corriente):
    for ups,battery,temp,capacity,load,life,current in zip(const.HOST_NAME,temp_bateria, temperatura_uio, capacidad_bateria, carga_salida, tiempo_autonomia, corriente):
        ups_aux = obtener_hostname(ups)
        print(f"ups_temp,host={ups_aux} battery={battery},temp={temp},capacity={capacity},load={load},life={life},current={current}")

def generar_sesiones():
    global sesiones
    for host in const.HOST_NAME:
        sesion_aux = Session(hostname=host, community='publicapc', version=2)
        sesiones.append(sesion_aux)

def obtener_datos():
    global temp_bateria, temp_uio, capacidad_bateria, carga_salida, tiempo_autonomia
    for sesion in sesiones:
        try:
            aux = sesion.get(const.OIDB)
            temp_bateria.append(aux.value)
            try:
                aux = sesion.get(const.OIDT)
                temp_uio.append(aux.value)
            except:
                aux = sesion.get(const.OIDTNEW)
                temp_uio.append(aux.value)
            aux = sesion.get(const.OIDCapacity)
            capacidad_bateria.append(aux.value)
            aux = sesion.get(const.OIDLOAD)
            carga_salida.append(aux.value)
            aux = sesion.get(const.OIDLife)
            tiempo_aux = (int(aux.value))/6000
            tiempo_autonomia.append(tiempo_aux)
            aux = sesion.get(const.OIDCurrent)
            corriente.append(aux.value)
        except EasySNMPTimeoutError as error:
        # easysnmp.exceptions.EasySNMPTimeoutError: Excepcion de tiempo de espera al conectar con el host remoto.   
            print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
            sys.exit(0)
        except Exception as error2:
            print(f"Ocurrió un error inesperado: {error2}. El programa terminará. ")
            sys.exit(0)

# Funcion principal
def main():
    generar_sesiones()
    obtener_datos()
    print_info(temp_bateria, temp_uio, capacidad_bateria, carga_salida, tiempo_autonomia, corriente)
    

if __name__ == "__main__":
    main()