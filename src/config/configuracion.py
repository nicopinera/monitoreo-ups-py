#!/usr/bin/env python3

import os

COMMUNITY = "publicapc"
VERSION_SNMP = 1

HOST_NAME_SHORT_F1 = ['f1r2u1','f1r3u1','f1r7u1','f1r9u1','f1r10u2','f1r11u1','f1r11u2'] # f1r2u2
HOST_NAME_SHORT_F2 = ['f2r1u1','f2r1u2','f2r2u1','f2r2u2','f2r3u1','f2r3u2','f2r4u1','f2r4u2','f2r7u1','f2r7u2','f2r9u2','f2r10u1','f2r10u2','f2r11u1','f2r11u2'] # ,'f2r9u1'
HOST_NAME_SHORT_F3 = ['f3r11u1','f3r11u2']

HOST_NAME_STATE = HOST_NAME_SHORT_F1 + HOST_NAME_SHORT_F2 + HOST_NAME_SHORT_F3

HOST_NAME_HUMEDAD = "f2r7u1"
HOST_NAME_DC = "ups-dc"

SUFIJO = '.psi.unc.edu.ar'

FP_OUT = 0.95

OID_AUTONOMIA = '1.3.6.1.4.1.534.1.2.1.0'
OID_CARGA_BATERIA = '1.3.6.1.4.1.534.1.2.4.0'
OID_TEMP_BATERIA = '1.3.6.1.2.1.33.1.2.7.0'
OID_CARGA_OUT = '1.3.6.1.4.1.534.1.4.1.0'
OID_CORRIENTE_OUT_F1 = '1.3.6.1.4.1.534.1.4.4.1.3.1'
OID_CORRIENTE_OUT_F2 = '1.3.6.1.4.1.534.1.4.4.1.3.2'
OID_CORRIENTE_OUT_F3 = '1.3.6.1.4.1.534.1.4.4.1.3.3'
OID_VOLTAJE_OUT = '1.3.6.1.4.1.534.1.4.4.1.2.1'
OID_V_AN = '1.3.6.1.4.1.534.1.3.4.1.2.1'
OID_V_BN = '1.3.6.1.4.1.534.1.3.4.1.2.2'
OID_V_CN = '1.3.6.1.4.1.534.1.3.4.1.2.3'
OID_V_OUT_AN = '1.3.6.1.4.1.534.1.4.4.1.2.1'
OID_V_OUT_BN = '1.3.6.1.4.1.534.1.4.4.1.2.2'
OID_V_OUT_CN = '1.3.6.1.4.1.534.1.4.4.1.2.3'

# Temperaturas de las baterias
OIDB='1.3.6.1.4.1.318.1.1.1.2.2.2.0'

# Temperatura del sensor en UIO
OIDT='1.3.6.1.4.1.318.1.1.10.2.3.2.1.4.1'

# Algunos UPS no reconocen como UIO sino como algo externo
OIDTNEW='1.3.6.1.4.1.318.1.4.5.2.1.1.13'

# Carga de la bateria en %
OIDCAPACITY='1.3.6.1.4.1.318.1.1.1.2.2.1.0'

# Carga a la salida del UPS
OIDLOAD="1.3.6.1.4.1.318.1.1.1.4.2.3.0"

# Tiempo de autonomia
OIDLIFE="1.3.6.1.4.1.318.1.1.1.2.2.3.0"

# Corriente de salida en Ampers
OIDCURRENT="1.3.6.1.4.1.318.1.1.1.4.2.4.0"

OID_DC={
    "autonomia": OID_AUTONOMIA,
    "carga_bat":OID_CARGA_BATERIA,
    "bat_temp":OID_TEMP_BATERIA,
    "carga_out": OID_CARGA_OUT,
    "corriente_out_f1":OID_CORRIENTE_OUT_F1,
    "corriente_out_f2":OID_CORRIENTE_OUT_F2,
    "corriente_out_f3":OID_CORRIENTE_OUT_F3,
    "voltaje_out":OID_VOLTAJE_OUT,
    "voltaje_an_input":OID_V_AN,
    "voltaje_bn_input":OID_V_BN,
    "voltaje_cn_input":OID_V_CN,
    "voltaje_out_an": OID_V_OUT_AN,
    "voltaje_out_bn": OID_V_OUT_BN,
    "voltaje_out_cn": OID_V_OUT_CN
}

OID_UPS={
    "battery":OIDB,
    "capacity": OIDCAPACITY,
    "load":OIDLOAD,
    "life":OIDLIFE,
    "current":OIDCURRENT    
}

OID_HUMEDAD = '1.3.6.1.4.1.318.1.1.25.1.2.1.7.2.1'

VALOR_TEMP_BAT_MAX = 28
VALOR_TEMP_UIO_MAX = 28
VALOR_CARGA_MIN = 70
VALOR_LOAD_MAX = 45
VALOR_AUTONOMIA_MIN = 9.0

RUTA_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ARCHIVO_ENV = os.path.join(RUTA_RAIZ,'.env')
ARCHIVO_DB = os.path.join(RUTA_RAIZ,'data','errores.db')
ARCHIVO_CREACION_TABLA_STATE = os.path.join(RUTA_RAIZ,'data','creacion_tabla_state.sql')
VAR_PASSWORDCHAT = 'PASSWORDCHAT'

LOGS_DIR = os.path.join(RUTA_RAIZ, "logs")
APP_LOG_FILE = os.path.join(LOGS_DIR, "app.log")
ERROR_LOG_FILE = os.path.join(LOGS_DIR, "errors.log")


