#!/usr/bin/python3    

import constantes as const
from Sesiones import UPS
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Funcion principal
def main():
    load_dotenv()
    url = os.getenv('PASSWORDCHAT')
    ups_list = []
    for host in const.HOST_NAME_SHORT:
        ups = UPS(host)
        ups_list.append(ups)
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        for ups in ups_list:
            executor.submit(ups.validar_datos())

if __name__ == "__main__":
    main()