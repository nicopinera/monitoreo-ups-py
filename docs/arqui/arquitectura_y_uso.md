# Módulo de Monitoreo UPS

El presente software tiene como fin monitorear diferentes UPS, desde modelos estándar (APC) hasta equipos industriales trifásicos. Se utiliza una **Arquitectura Limpia**, lo que permite cambiar piezas (como la base de datos o el sistema de chat) sin romper el resto del programa.

1. [Arquitectura Simplificada](#arquitectura-simplificada)
    1. [Core/Dominio](#1-core--dominio-el-manual-de-reglas)
    2. [Drivers](#2-drivers-los-especialistas)
    3. [Infraestructura](#3-infraestructura)
    4. [Orquestador](#4-orquestador-el-director-de-orquesta)
2. [Como usar](#guía-de-uso-cómo-agregar-un-nuevo-ups)
3. [Ciclo de Vida](#ciclo-de-vida-de-una-alerta)

## Arquitectura Simplificada

Para entender el sistema, imagina una cadena de responsabilidades dividida en capas:

### 1. Core / Dominio (El "Manual de Reglas")

En esta capa de la arquitectura se encuentra el dominio (logica de negocio) y las entidades necesarias para nuestro sistema. En nuestro caso la logica de negocio viene dada por la validacion de los datos obtenidos por los UPS. Las dos entidades principales que estan involucradas en nuestro sistema son los **Errores** y **UPSBase**, siendo este ultimo el esquelto/contrato que deben cumplir todas las implementaciones de UPS que se agreguen al sistema.

- **Validaciones:** Funciones matemáticas que dicen: "Si la carga es < 10, devuelve un Error de Carga Baja". Son funciones puras y fáciles de testear.
- **Errores:** Un catálogo centralizado (Enum) con todos los tipos de problemas posibles.
- **UPSBase:** El contrato que define que todo UPS debe saber **Recolectar**, **Validar** e **Imprimir** sus datos.

### 2. Drivers (Los "Especialistas")

Cada archivo en esta carpeta es un experto en un tipo de UPS:

- **StateUPS:** Sabe monitorear temperatura, carga y load de baterias, temperatura ambiente, corriente de salida.
- **DC_UPS:** Sabe calcular potencias trifásicas y obtener datos especificos.
- **Hum_UPS:** Se enfoca únicamente en sensores de humedad.

### 3. Infraestructura

Son los módulos que hablan con el mundo exterior.

- **Cliente SNMP:** Pide datos a los equipos. No sabe qué significan los números, solo los trae.
- **Notificador:** Envía mensajes a Google Chat. No sabe por qué hay una alerta, solo entrega el mensaje.
- **Repositorio DB:** Guarda y recupera errores en SQLite usando un "candado" (Lock) para que no haya choques al usar varios hilos.

### 4. Orquestador (El "Director de Orquesta")

Es el archivo `main.py`. Su trabajo es:

1. Leer la configuración.
2. Crear una lista de UPS a monitorear.
3. Repartir el trabajo en hilos (**Multithreading**) para que el monitoreo sea rápido.

---

## Guía de Uso: ¿Cómo agregar un nuevo UPS?

Si mañana necesitas monitorear un nuevo modelo de UPS, solo sigue estos 3 pasos:

### Paso 1: Configura los OIDs

En `src/config/configuracion.py`, agrega un diccionario con los OIDs del nuevo equipo.

```python
NUEVA_UPS_OIDS = { "voltaje": "1.3.6.1...", "carga": "1.3.6.1..." }
```

### Paso 2: Crea el Driver

Si la lógica es muy distinta a las actuales, crea un archivo en `src/drivers/nuevo_modelo.py` que herede de `BaseUPS`. Si es similar a una actual, puedes reutilizar el Driver existente.

### Paso 3: Regístralo en Main

En `src/main.py`, agrega la instancia a la lista de ejecución:

```python
mis_ups = [
    StateUPS("ups-central", snmp, notifier, db),
    NuevoModeloUPS("ups-nueva", snmp, notifier, db)
]
```

## Ciclo de Vida de una Alerta

1. El **Driver** pide datos por **SNMP**.
2. El **Driver** le pregunta a **Validación** si los datos están bien.
3. Si hay error, el **Driver** le pide a la **DB** que lo registre.
4. Si es un error nuevo (o uno que se volvió a producir), la **DB** confirma y el **Driver** le pide al **Notificador** que avise por chat.
5. Finalmente, el **Driver** imprime una línea de texto que **Telegraf/Grafana** recolectan automáticamente.
