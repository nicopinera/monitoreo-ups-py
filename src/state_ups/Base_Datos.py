import sqlite3, os
import constantes as c

class BaseDatos():
    def __init__(self,db_file):
        self.db_file = db_file # Direccion de la base de datos
        self.conn = None # Conexion a la misma
    
    def Crear_Base_datos(self):
        """
        Creacion de la base de datos

        Si no existe el archivo, lo crea y genera la tabla errores dentro de la base de datos.
        La misma almacenara un id autoincremental del error, el host del ups, el tipo de error, el estado del mismo
        y una fecha que se genera con la fecha y hora actual.
        """
        self.conn = sqlite3.connect(self.db_file)
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS errores(
            id INTEGER PRIMARY KEY,
            ups_host TEXT NOT NULL,
            tipo_error TEXT NOT NULL,
            estado_error TEXT NOT NULL CHECK (estado_error IN ('activo', 'resuelto')),
            fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        self.conn.close()
    
    def conectar_DB(self):
        self.conn = sqlite3.connect(self.db_file)
        return self.conn # Se conecta a la base de datos
    
    def desconectar_DB(self):
        self.conn.close()
        self.conn = None # Cierra la conexion a la base de datos
    
    def error_activo(self,ups_host,tipo_error):
        # Busca errores activos especificos de un UPS y devuelve algo distinto de None si encontro, 
        # si no encontro ningun error devuelve None
        self.conectar_DB()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM errores WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",(ups_host,tipo_error)
        )
        resultado = cursor.fetchone() # Si encuentra algo devuelve algo distinto de None
        self.desconectar_DB()
        return resultado

    def error_resuelto(self,ups_host,tipo_error):
        # Busca si el error de un determinado host ya fue resuelto
        self.conectar_DB()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM errores WHERE ups_host=? AND tipo_error=? AND estado_error='resuelto'",(ups_host,tipo_error)
            )
        reusultado = cursor.fetchone()
        self.desconectar_DB()
        return reusultado
    
    def agregar_error(self,ups_host,tipo_error):
        # Agrega un error a la base de datos
        self.conectar_DB()
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO errores (ups_host, tipo_error, estado_error) VALUES (?, ?, 'activo')",(ups_host,tipo_error)
            )
        self.conn.commit()
        self.desconectar_DB()
    
    def resolver_error(self,ups_host,tipo_error):
        # Cambia el estado y la fecha de un error
        self.conectar_DB()
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE errores SET estado_error='resuelto',fecha=CURRENT_TIMESTAMP WHERE ups_host=? AND tipo_error=? AND estado_error='activo'",(ups_host,tipo_error)
            )
        self.conn.commit()
        self.desconectar_DB()