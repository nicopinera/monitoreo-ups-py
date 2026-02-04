#!/usr/bin/python3 

import constantes as const
from easysnmp import Session, EasySNMPTimeoutError
import sys

def obtener_datos(sesion_snmp):
    oid = {
        "autonomia": const.OID_AUTONOMIA,
        "carga_bat":const.OID_CARGA_BATERIA,
        "bat_temp":const.OID_TEMP_BATERIA,
        "carga_out": const.OID_CARGA_OUT,
        "corriente_out_f1":const.OID_CORRIENTE_OUT_F1,
        "corriente_out_f2":const.OID_CORRIENTE_OUT_F2,
        "corriente_out_f3":const.OID_CORRIENTE_OUT_F3,
        "voltaje_out":const.OID_VOLTAJE_OUT,
        "voltaje_an":const.OID_V_AN,
        "voltaje_bn":const.OID_V_BN,
        "voltaje_cn":const.OID_V_CN,
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
        print(f"dc-ups,host={ups} autonomia={datos['autonomia']}")
        print(f"dc-ups,host={ups} carga_bat={datos['carga_bat']}")
        print(f"dc-ups,host={ups} bat_temp={datos['bat_temp']}")
        print(f"dc-ups,host={ups} carga_out={datos['carga_out']}")
        print(f"dc-ups,host={ups} corriente_out_f1={datos['corriente_out_f1']},corriente_out_f2={datos['corriente_out_f2']},corriente_out_f3={datos['corriente_out_f3']}")
        print(f"dc-ups,host={ups} voltaje_out={datos['voltaje_out']}")
        print(f"dc-ups,host={ups} voltaje_an={datos['voltaje_an']},voltaje_bn={datos['voltaje_bn']},voltaje_cn={datos['voltaje_cn']}")
    except EasySNMPTimeoutError as error:
        # easysnmp.exceptions.EasySNMPTimeoutError: Excepcion de tiempo de espera al conectar con el host remoto.   
        print(f"Ocurrió un error inesperado: {error}. El programa terminará. ")
        sys.exit(0)
    except Exception as error2:
        print(f"Ocurrió un error inesperado: {error2}. El programa terminará. ")
        sys.exit(0)

if __name__ == "__main__":
    main()