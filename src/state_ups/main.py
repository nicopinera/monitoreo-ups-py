#!/usr/bin/python3    

import constantes as const
import os, time
from Sesiones import UPS
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

def borrar_si_vieja(db_path,minutos=10):
    if os.path.exists(db_path):
        edad = (time.time() - os.path.getmtime(db_path)) / 60
        if edad > minutos:
            os.remove(db_path)

# Funcion principal
def main():
    borrar_si_vieja(const.DIR_DB) # Se borra cada 10 min
    load_dotenv()
    url = os.getenv('PASSWORDCHAT')
    ups_list = []
    for host in const.HOST_NAME_SHORT:
        ups = UPS(host,url,const.DIR_DB)
        ups_list.append(ups)
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        for ups in ups_list:
            executor.submit(ups.validar_datos)

if __name__ == "__main__":
    main()