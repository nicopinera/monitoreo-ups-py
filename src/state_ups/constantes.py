# Listado de los UPS a monitorear
HOST_NAME_SHORT_F1 = ['f1r2u1','f1r3u1','f1r7u1','f1r9u1','f1r10u2','f1r11u1','f1r11u2'] # f1r2u2
HOST_NAME_SHORT_F2 = ['f2r1u1','f2r1u2','f2r2u1','f2r2u2','f2r3u1','f2r3u2','f2r4u1','f2r4u2','f2r7u1','f2r7u2','f2r9u2','f2r10u1','f2r10u2','f2r11u1','f2r11u2'] # ,'f2r9u1'
HOST_NAME_SHORT_F3 = ['f3r11u1','f3r11u2']

HOST_NAME_SHORT = HOST_NAME_SHORT_F1 + HOST_NAME_SHORT_F2 + HOST_NAME_SHORT_F3

# Nombre de comunidad configurado en SNMP dentro de los UPS con tu IP
COMMUNITY = 'publicapc'

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

DIR_DB = "src/state_ups/errores.db"

VALOR_TEMP_BAT_MAX = 23
VALOR_TEMP_UIO_MAX = 23
VALOR_CARGA_MIN = 70
VALOR_LOAD_MAX = 45
VALOR_AUTONOMIA_MIN = 9.0
