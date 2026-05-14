#!/usr/bin/python3
"""Enumeración de tipos de errores de UPS.

Este módulo define todos los estados de error posibles que pueden detectarse
durante el monitoreo de UPS, incluyendo problemas de temperatura de batería,
fallas de sensores y problemas de capacidad.
"""

from enum import Enum

class Errores(Enum):
    """Enumeración de tipos de error del monitoreo UPS.

    Atributos:
        TEMPERATURA_BATERIA_ALTA: La temperatura de la batería excede el umbral seguro.
        UIO_ROTO: El sensor ambiental (UIO) está desconectado o roto.
        UIO_TEMPERATURA_ALTA: La temperatura ambiental excede el umbral seguro.
        CARGA_MINIMA: El nivel de carga de la batería cae por debajo del umbral mínimo.
        LOAD_MAXIMO: La carga de salida excede el umbral máximo permitido.
        AUTONOMIA_MINIMO: El tiempo de autonomía cae por debajo del umbral mínimo.
    """
    TEMPERATURA_BATERIA_ALTA = 1
    UIO_ROTO = 2
    UIO_TEMPERATURA_ALTA = 3
    CARGA_MINIMA = 4
    LOAD_MAXIMO = 5
    AUTONOMIA_MINIMO = 6
