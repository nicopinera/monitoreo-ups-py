#!/usr/bin/python3

from abc import ABC, abstractmethod

"""Interfaz de UPS"""


class BaseUPS(ABC):
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
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
    def lineas_telegraf(self):
        """
        Cada driver arma sus lineas para grafana/telegraf y las devuelve como lista de str.
        No imprime: la salida la escribe main desde el hilo principal (ver main.escribir_lineas).
        """
        pass

    @abstractmethod
    def ejecutar(self):
        """Lee, valida y devuelve las lineas de telegraf del equipo."""
        pass

    def _formatear_campos(self, campos):
        """
        Arma los campos de una linea de telegraf ("a=1,b=2") omitiendo los que no tienen dato.
        Devuelve "" si ninguno tiene dato (una linea sin campos es invalida en line protocol).
        """
        return ",".join(
            f"{campo}={self.datos[campo]}" for campo in campos if self.datos.get(campo) is not None
        )
