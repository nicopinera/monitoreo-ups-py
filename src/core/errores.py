from enum import Enum

class Errores(Enum):
    TEMPERATURA_BATERIA_ALTA = 1 # El nombre es un str y el numero int
    UIO_ROTO = 2
    UIO_TEMPERATURA_ALTA = 3
    CARGA_MINIMA = 4
    LOAD_MAXIMO = 5
    AUTONOMIA_MINIMO = 6
