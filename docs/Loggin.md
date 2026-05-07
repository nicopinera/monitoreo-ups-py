# Mejor Uso para monitoreo de UPS: 
1.*MEJOR NO* DEBUG: Detalles técnicos (OIDs, respuestas SNMP crudas).EJ: logger.debug("OID consultado: 1.3.6.1...")  
2. *MEJOR NO* INFO: Eventos normales (UPS conectado, métrica registrada). EJ: logger.info("UPS conectado exitosamente")
3. WARNING: Anomalías no críticas (humedad alta, batería próxima a vencer). EJ: logger.warning("Voltaje bajo: 100V")
4. ERROR: Fallos en conexión, DB o procesamiento. EJ: logger.error("No se pudo conectar a DB")
5. CRITICAL: Sistema completamente no funcional. EJ: logger.critical("Fallo de energia principal")


# 5 Pasos para Implementar Logging

## PASO 1: Entender la Configuración de Logging (Teoría + Diseño)
1. ¿Donde van los logs?

    Archivo principal: *logs/app.log* (todos los eventos)

    Archivo de errores: *logs/errors.log* (solo ERROR y CRITICAL)

    Consola: Solo INFO+ (para monitoreo en vivo)

2. ¿Qué información incluir?

    Timestamp exacto (para correlacionar con Grafana)

    Nombre del logger (cuál módulo escribió el log)

    Nivel de severidad

    ensaje + excepciones si aplica

3. ¿Rotación de logs?

Los logs pueden crecer mucho. Usar *RotatingFileHandler* para crear nuevos archivos automáticamente (ej. cada 10 MB o cada día).

4. ¿Salida de Telegraf?

*Crítico:* Las líneas de Telegraf (dc-ups,host=...) NUNCA deben ir a logs. Van solo a stdout (para que Telegraf las capture).

ESTRUCTURA PROPPUESTA

logs/
  ├── app.log              (todos los eventos)
  ├── errors.log           (solo errores críticos)
  ├── telegraf.log         (solo métricas, para auditoria)
  └── backup/              (logs rotados)

## PASO 2: Crear un Módulo Centralizado de Logging
¿Para que?
    Evitas configurar logging en cada archivo.
    Cambios globales en un solo lugar.
    Reutilizable en la app web y el monitoreo.

### Codigo en //src/config/logger.py
RotatingFileHandler: Crea archivos de backup automáticamente cuando alcanzan un tamaño.

logging.Formatter: Define el formato (timestamp, nombre, nivel, mensaje).

logger_raiz.setLevel(DEBUG) + handlers con niveles más altos = filtrado flexible.

## PASO 3: Implementar Logging en Módulos Existentes

Objetivo: Reemplazar print() y sys.stderr con llamadas a logger en cada módulo.

Módulos a actualizar (en orden de prioridad):

1. database.py (crítico: fallos de DB)
2. snmp_client.py (crítico: conexión)
3. src/drivers/ups_base.py y sus subclases (estado del monitoreo)
4. configuracion.py (carga de config)
5. main.py (orquestación)
Ejemplo de cómo actualizar en .databasev2.py:
Cambios principales:
import logging + obtener_logger(__name__)
Reemplazar print() con logger.info(), logger.error(), etc.
exc_info=True captura el full traceback en caso de excepción.

## PASO 4: Separar Salida de Métricas (Grafana) de Logs

Objetivo: Las líneas de Telegraf no deben pasar por logging. Van directo a stdout.

El problema:
### Actual (MALO)
print(f"dc-ups,host={self.hostname} {campos}")  # Telegraf lo captura
logger.info(...)  # También podría contaminar la salida


### La solución:

Crear un logger específico para Telegraf que solo escribe a stdout sin timestamp


## PASO 5: Configurar Niveles y Testar
Objetivo: Asegurar que el logging funciona correctamente en todos los escenarios.

Crear mainv2.py actualizado:

# Resumen Visual del Sistema de Logging

┌─────────────────────────────────────────────────────────────┐
│  Módulos del Proyecto                                       │
│  (database.py, snmp_client.py, drivers/*.py)                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ├─→ logger.info("...")      (Evento normal)
                 ├─→ logger.warning("...")   (Anomalía)
                 ├─→ logger.error("...")     (Fallo)
                 └─→ logger_telegraf.info()  (Métrica)
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
    Archivo       Archivo       Consola
   app.log      errors.log     (stdout)
   (todos)      (solo ERROR)   (INFO+)
       │              │
       └──────────────┼──────────────┘
                      │
              Telegraf/Grafana
            (captura stdout puro)