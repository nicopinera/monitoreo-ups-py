#!/usr/bin/python3

import config.configuracion as c
from core.errores import Errores

def validar_temp_bateria(valor):
    """
    Valida la temperatura de las baterias, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de temperatura obtenido
    """
    aux = float(valor)
    if (aux > c.VALOR_TEMP_BAT_MAX):
        error = Errores.TEMPERATURA_BATERIA_ALTA
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} [°C]*"
        return error,msg
    return None,None

def validar_temp_uio(valor):
    """
    Valida la temperatura del UIO, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de temperatura obtenido
    """
    aux = float(valor)
    if aux < 0:
        error = Errores.UIO_ROTO
        msg = "[ADVERTENCIA] Sensor de Temperatura Roto"
        return error,msg
    elif aux > c.VALOR_TEMP_UIO_MAX:
        error = Errores.UIO_TEMPERATURA_ALTA
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} [°C]*"
        return error,msg
    return None,None

def validar_carga(valor):
    """
    Valida la carga de las baterias, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de carga obtenido
    """
    aux = float(valor)
    if aux < c.VALOR_CARGA_MIN:
        error = Errores.CARGA_MINIMA
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} %*"
        return error,msg
    return None,None

def validar_load(valor):
    """
    Valida la carga a la salida del UPS, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de load obtenido
    """
    aux = float(valor)
    if aux > c.VALOR_LOAD_MAX:
        error = Errores.LOAD_MAXIMO
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} %*"
        return error,msg
    return None,None

def validar_tiempo_autonomia(valor):
    """
    Valida el tiempo de autonomia del UPS, si se encuentra en nivel critico
    genera tanto el error, como el mensaje de notificacion para el chat de google
    
    :param valor: Valor de autonomia obtenido
    """
    aux = float(valor)
    if aux < c.VALOR_AUTONOMIA_MIN:
        error = Errores.AUTONOMIA_MINIMO
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} [min]*"
        return error,msg
    return None,None