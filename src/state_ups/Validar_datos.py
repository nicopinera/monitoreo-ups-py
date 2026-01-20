import constantes as c

def validar_temp_bateria(valor,host):
    valido = True
    msg = ""
    if (int(valor) > c.VALOR_TEMP_BAT_MAX):
        valido = False
        msg = f"[ADVERTENCIA - {host}] Temperatura de bateria mayor a {c.VALOR_TEMP_BAT_MAX} : Valor actual {valor}. Tomar acciones pertinentes"
    return valido,msg

def validar_temp_uio(valor,host):
    aux = int(valor)
    valido = True
    msg = ""
    if aux == -1:
        valido = False
        msg = f"[ADVERTENCIA - {host}] Sensor de Temperatura Roto"
    elif aux > c.VALOR_TEMP_UIO_MAX:
        valido = False
        msg = f"[ADVERTENCIA - {host}] Temperatura Ambiental alta - Valor actual {valor}"
    return valido,msg

def validar_carga(valor,host):
    valido = True
    msg = ""
    return valido,msg

def vaildar_load(valor,host):
    valido = True
    msg = ""
    return valido,msg

def validar_tiempo_autonomia(valor,host):
    valido = True
    msg = ""
    aux = float(valor)
    if aux < c.VALOR_AUTONOMIA_MIN:
        valido = False
        msg = f"[ADVERTENCIA - {host}] Tiempo de autonomia bajo - Valor actual {valor}"
    return valido,msg

def validar_corriente(valor,host):
    valido = True
    msg = ""
    return valido,msg