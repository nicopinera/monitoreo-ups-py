import sqlite3
import config.configuracion as c
class RepositorioDB:
    def __init__(self,db_file):
        self.db_file = db_file
        self.conexion = sqlite3.connect(db_file)
        self.cursos = self.conexion.cursor()
        
        try:
            with open(c.ARCHIVO_CREACION_TABLA_STATE,'r', encoding="utf-8") as sql_script:
                tabla = sql_script.read()
            
            self.cursos.executescript(tabla)
            
            self.conexion.commit()
        except sqlite3.Error as e:
            print(f"Error al ejecutar el script de creacion de tablas: {e}")
        finally:
            self.conexion.close()
    
    def conectar_DB(self):
        self.conexion = sqlite3.connect(self.db_file)
        return self.conexion # Se conecta a la base de datos
    
    def desconectar_DB(self):
        self.conexion.close()
        self.conexion = None # Cierra la conexion a la base de datos