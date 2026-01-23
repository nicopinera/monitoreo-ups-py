import constantes as c
from Error_State import Errores

def validar_temp_bateria(valor,host):
    """
    Valida la temperatura de las baterias, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de temperatura obtenido
    :param host: Hostname del UPS
    """
    error = None
    msg = ""
    aux = float(valor)
    if (aux > c.VALOR_TEMP_BAT_MAX):
        error = Errores.TEMPERATURA_BATERIA_ALTA
        msg = f"[ADVERTENCIA - {host}] Temperatura de bateria mayor a {c.VALOR_TEMP_BAT_MAX} °C : Valor actual {valor} °C. Tomar acciones pertinentes"
    return error,msg

def validar_temp_uio(valor,host):
    """
    Valida la temperatura del UIO, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de temperatura obtenido
    :param host: Hostname del UPS
    """
    error = None
    msg = ""
    aux = float(valor)
    if aux < 0:
        error = Errores.UIO_ROTO
        msg = f"[ADVERTENCIA - {host}] Sensor de Temperatura Roto - REEMPLAZAR"
    elif aux > c.VALOR_TEMP_UIO_MAX:
        error = Errores.UIO_TEMPERATURA_ALTA
        msg = f"[ADVERTENCIA - {host}] Temperatura Ambiental alta - Valor actual {valor} °C"
    return error,msg

def validar_carga(valor,host):
    """
    Valida la carga de las baterias, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de carga obtenido
    :param host: Hostname del UPS
    """
    error = None
    msg = ""
    aux = float(valor)
    if aux < c.VALOR_CARGA_MIN:
        error = Errores.CARGA_MINIMA
        msg = f"[ADVERTENCIA - {host}] Carga de bateria baja - Valor actual {valor} %"
    return error,msg

def validar_load(valor,host):
    """
    Valida la carga a la salida del UPS, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de load obtenido
    :param host: Hostname del UPS
    """
    error = None
    msg = ""
    aux = float(valor)
    if aux > c.VALOR_LOAD_MAX:
        error = Errores.LOAD_MAXIMO
        msg = f"[ADVERTENCIA - {host}] Carga a la salida alta - Valor actual {valor} %"
    return error,msg

def validar_tiempo_autonomia(valor,host):
    """
    Valida el tiempo de autonomia del UPS, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de autonomia obtenido
    :param host: Hostname del UPS
    """
    error = None
    msg = ""
    aux = float(valor)
    if aux < c.VALOR_AUTONOMIA_MIN:
        error = Errores.AUTONOMIA_MINIMO
        msg = f"[ADVERTENCIA - {host}] Tiempo de autonomia bajo - Valor actual {valor} min"
    return error,msg