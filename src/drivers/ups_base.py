from abc import ABC, abstractmethod

class BaseUPS(ABC):
    def __init__(self,hostname,clienteSNMP,notificador=None,rep_db=None):
        self.hostname = hostname
        self.clienteSNMP = clienteSNMP
        self.notificador = notificador
        self.rep_db = rep_db
        self.datos = {}
    
    @abstractmethod
    def obtener_datos(self):
        """Cada driver debe saber que OID pedir"""
        pass
    
    @abstractmethod
    def validar_datos_y_notificar(self):
        """Cada driver tiene sus propia logica para validar y generar las alertas"""
        pass

    @abstractmethod
    def imprimir_telegraf(self):
        """Cada driver imprime su formato para grafana/telegraf"""
        pass
    
    def ejecutar(self):
        """Este metodo que se llama en main"""
        self.obtener_datos()
        self.imprimir_telegraf()
        if self.notificador and self.rep_db:
            self.validar_datos_y_notificar()