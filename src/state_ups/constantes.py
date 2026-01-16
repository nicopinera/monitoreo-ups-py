# Listado de los UPS a monitorear
HOST_NAME_SHORT = ['f1r2u1','f1r2u2','f1r3u1','f1r7u1','f1r9u1','f1r10u2','f1r11u1','f1r11u2','f2r7u1']

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


