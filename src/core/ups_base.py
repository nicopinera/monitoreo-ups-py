#!/usr/bin/python3
"""Clase base abstracta para drivers UPS.

Define la interfaz que todas las implementaciones de drivers UPS deben seguir.
Provee un contrato para la colección de datos, validación e informes.
"""

from abc import ABC, abstractmethod

class BaseUPS(ABC):
    """Clase base abstracta para drivers de monitoreo UPS.

    Todas las implementaciones de drivers UPS (StateUPS, DataCenterUPS,
    HumedadUPS) heredan de esta clase y deben implementar los métodos
    abstractos requeridos para colección de datos, validación e informes.

    Atributos:
        hostname (str): Identificador corto del host UPS.
        clienteSNMP: Cliente SNMP para comunicación con el UPS.
        notificador: Servicio de notificaciones (Google Chat).
        rep_db: Repositorio de base de datos para persistencia de errores.
        datos (dict): Diccionario con métricas recogidas del UPS.
    """
    def __init__(self, hostname, clienteSNMP, notificador=None, rep_db=None):
        self.hostname = hostname
        self.clienteSNMP = clienteSNMP
        self.notificador = notificador
        self.rep_db = rep_db
        self.datos = {}

    @abstractmethod
    def obtener_datos(self):
        """Recuperar métricas del UPS vía SNMP.

        Cada implementación conoce qué OIDs consultar según el modelo y las
        capacidades específicas del UPS.

        Raises:
            NotImplementedError: Este método abstracto debe implementarse en
                las subclases.
        """
        pass

    @abstractmethod
    def validar_datos_y_notificar(self):
        """Validar métricas recopiladas y enviar notificaciones si es necesario.

        Cada driver implementa su propia lógica de validación basada en reglas de
        umbrales y criterios de detección de errores. Las notificaciones se
        envían solo cuando se detectan errores o se resuelven.

        Raises:
            NotImplementedError: Este método abstracto debe implementarse en
                las subclases.
        """
        pass

    @abstractmethod
    def imprimir_telegraf(self):
        """Generar salida de métricas en formato compatible con Telegraf/Grafana.

        Imprime las métricas recopiladas en formato InfluxDB line protocol,
        que Telegraf consume para ingesta en InfluxDB y visualización en Grafana.

        Raises:
            NotImplementedError: Este método abstracto debe implementarse en
                las subclases.
        """
        pass

    @abstractmethod
    def ejecutar(self):
        """Ejecutar el ciclo completo de monitoreo.

        Orquesta el flujo completo de monitoreo: recopilación de datos,
        validación y salida. La implementación varía según el tipo de driver.

        Raises:
            NotImplementedError: Este método abstracto debe implementarse en
                las subclases.
        """
        pass
