#!/usr/bin/python3    

import constantes as const
from Sesiones import UPS

# Funcion principal
def main():
    contador = 0
    for host in const.HOST_NAME_SHORT:
        ups = UPS(host)
        ups.toString()
        contador += 1
    print(f"Se monitorizaron {contador} UPS")

if __name__ == "__main__":
    main()