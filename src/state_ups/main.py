#!/usr/bin/python3    

import constantes as const
from Sesiones import UPS

# Funcion principal
def main():
    for host in const.HOST_NAME_SHORT:
        ups = UPS(host)
        ups.toString()

if __name__ == "__main__":
    main()