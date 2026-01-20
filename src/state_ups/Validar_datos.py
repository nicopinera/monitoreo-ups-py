import constantes as c

def validar_temp_bateria(valor,host):
    valido = False
    msg = ""
    if (valor >=c.VALOR_TEMP_BAT_MAX):
        valido = False
        msg = f"[ADVERTENCIA - {host}] Temperatura de bateria mayor a {c.VALOR_TEMP_BAT_MAX} : Valor actual {valor}. Tomar acciones pertinentes"
    return valido,msg

def validar_temp_uio(valor,host):
    valido = False
    msg = ""
    return valido,msg

def validar_carga(valor,host):
    valido = False
    msg = ""
    return valido,msg

def vaildar_load(valor,host):
    valido = False
    msg = ""
    return valido,msg

def validar_tiempo_autonomia(valor,host):
    valido = False
    msg = ""
    return valido,msg

def validar_corriente(valor,host):
    valido = False
    msg = ""
    return valido,msg