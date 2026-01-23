#!/usr/bin/python3    

import constantes as const
import os, time,sqlite3
from Sesiones import UPS
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

def borrar_si_vieja(db_path,minutos=10):
    """Borra la base de datos solo si no está en uso y es vieja"""
    if os.path.exists(db_path):
        try:
            # Intentar abrir la base de datos para ver si está en uso
            conn = sqlite3.connect(db_path)
            conn.close()
            # Si se pudo conectar, verificar edad
            edad = (time.time() - os.path.getmtime(db_path)) / 60
            if edad > minutos:
                os.remove(db_path)
                # print(f"[INFO] Base de datos {db_path} eliminada por ser mayor a {minutos} minutos")
        except Exception as e:
            pass
            # print(f"[WARNING] No se pudo borrar {db_path}: {e}")

# Funcion principal
def main():
    borrar_si_vieja(const.DIR_DB)
    load_dotenv("/etc/telegraf/monitoreo-ups/.env")
    url = os.getenv('PASSWORDCHAT')
    #print(f"[DEBUG] PASSWORDCHAT cargado: {url}")
    
    ups_list = []
    for host in const.HOST_NAME_SHORT:
        ups = UPS(host,url,const.DIR_DB)
        ups_list.append(ups)
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        for ups in ups_list:
            executor.submit(ups.validar_datos)

if __name__ == "__main__":
    main()