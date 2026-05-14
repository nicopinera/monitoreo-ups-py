#!/usr/bin/python3
"""Funciones de validación de datos UPS.

Este módulo provee funciones de validación para todas las métricas del
monitoreo UPS. Cada función verifica si una métrica excede o está por debajo
al umbral configurado y devuelve códigos de error junto con mensajes para
Google Chat.

Las funciones retornan tuplas con:
    - error: Errores | None
    - mensaje: str | None
"""

import config.configuracion as c
from core.errores import Errores


def validar_temp_bateria(valor):
    """Validar temperatura de batería contra el umbral de seguridad.

    Verifica si la temperatura de la batería excede el valor máximo
    configurado y genera un código de error con mensaje de notificación.

    Args:
        valor: Temperatura de batería en grados Celsius.

    Returns:
        tuple: (Errores.TEMPERATURA_BATERIA_ALTA, mensaje_formateado) si la
            temperatura excede VALOR_TEMP_BAT_MAX, de lo contrario (None, None).

    Raises:
        ValueError: Si valor no puede convertirse a float.
    """
    aux = float(valor)
    if aux > c.VALOR_TEMP_BAT_MAX:
        error = Errores.TEMPERATURA_BATERIA_ALTA
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} [°C]*"
        return error, msg
    return None, None


def validar_temp_uio(valor):
    """Validar sensor ambiental (UIO) de temperatura.

    Comprueba si el sensor UIO está operativo (valor >= 0) y si la temperatura
    se mantiene dentro de los límites seguros. Valores negativos indican falla.

    Args:
        valor: Temperatura ambiental en grados Celsius.

    Returns:
        tuple: (error, mensaje) donde:
            - (Errores.UIO_ROTO, msg) si valor < 0
            - (Errores.UIO_TEMPERATURA_ALTA, msg) si valor > VALOR_TEMP_UIO_MAX
            - (None, None) si el sensor funciona y la temperatura es normal.

    Raises:
        ValueError: Si valor no puede convertirse a float.
    """
    aux = float(valor)
    if aux < 0:
        error = Errores.UIO_ROTO
        msg = "[ADVERTENCIA] Sensor de Temperatura Roto"
        return error, msg
    elif aux > c.VALOR_TEMP_UIO_MAX:
        error = Errores.UIO_TEMPERATURA_ALTA
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} [°C]*"
        return error, msg
    return None, None


def validar_carga(valor):
    """Validar nivel de carga de la batería.

    Comprueba si el porcentaje de carga de la batería cumple con el umbral
    mínimo configurado.

    Args:
        valor: Nivel de carga de la batería en porcentaje (0-100).

    Returns:
        tuple: (Errores.CARGA_MINIMA, mensaje_formateado) si la carga está por
            debajo de VALOR_CARGA_MIN, de lo contrario (None, None).

    Raises:
        ValueError: Si valor no puede convertirse a float.
    """
    aux = float(valor)
    if aux < c.VALOR_CARGA_MIN:
        error = Errores.CARGA_MINIMA
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} %*"
        return error, msg
    return None, None


def validar_load(valor):
    """Validar porcentaje de carga de salida del UPS.

    Comprueba si la carga de salida excede el umbral máximo configurado.

    Args:
        valor: Porcentaje de carga de salida (0-100).

    Returns:
        tuple: (Errores.LOAD_MAXIMO, mensaje_formateado) si la carga supera
            VALOR_LOAD_MAX, de lo contrario (None, None).

    Raises:
        ValueError: Si valor no puede convertirse a float.
    """
    aux = float(valor)
    if aux > c.VALOR_LOAD_MAX:
        error = Errores.LOAD_MAXIMO
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} %*"
        return error, msg
    return None, None


def validar_tiempo_autonomia(valor):
    """Validar tiempo de autonomía restante del UPS.

    Comprueba si el tiempo de autonomía restante cumple con el umbral mínimo
    configurado.

    Args:
        valor: Tiempo de autonomía en minutos.

    Returns:
        tuple: (Errores.AUTONOMIA_MINIMO, mensaje_formateado) si la autonomía
            está por debajo de VALOR_AUTONOMIA_MIN, de lo contrario (None, None).
    """
    aux = float(valor)
    if aux < c.VALOR_AUTONOMIA_MIN:
        error = Errores.AUTONOMIA_MINIMO
        msg = f"[ADVERTENCIA] *{error.name}*: Valor actual *{valor} [min]*"
        return error, msg
    return None, None
