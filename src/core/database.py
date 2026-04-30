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

    def error_activo(self,ups_host,tipo_error):
        # Busca errores activos especificos de un UPS y devuelve algo distinto de None si encontro, 
        # si no encontro ningun error devuelve None
        self.conectar_DB()
        cursor = self.conexion.cursor()
        cursor.execute(
            "SELECT * FROM errores WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",(ups_host,tipo_error)
        )
        resultado = cursor.fetchone() # Si encuentra algo devuelve algo distinto de None
        self.desconectar_DB()
        return resultado

    def error_resuelto(self,ups_host,tipo_error):
        # Busca si el error de un determinado host ya fue resuelto
        self.conectar_DB()
        cursor = self.conexion.cursor()
        cursor.execute(
            "SELECT * FROM errores WHERE ups_host=? AND tipo_error=? AND estado_error='resuelto'",(ups_host,tipo_error)
            )
        reusultado = cursor.fetchone()
        self.desconectar_DB()
        return reusultado
    
    def agregar_error(self,ups_host,tipo_error):
        # Agrega un error a la base de datos
        self.conectar_DB()
        cursor = self.conexion.cursor()
        cursor.execute(
            "INSERT INTO errores (ups_host, tipo_error, estado_error) VALUES (?, ?, 'activo')",(ups_host,tipo_error)
            )
        self.conn.commit()
        self.desconectar_DB()
    
    def resolver_error(self,ups_host,tipo_error):
        # Cambia el estado y la fecha de un error
        self.conectar_DB()
        cursor = self.conexion.cursor()
        cursor.execute(
            "UPDATE errores SET estado_error='resuelto',fecha=CURRENT_TIMESTAMP WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",(ups_host,tipo_error)
            )
        self.conn.commit()
        self.desconectar_DB()