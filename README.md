# Monitoreo UPS

La idea del presente proyecto es simplificar la monitorizacion de todos los ups que se encuentran dentro del data center de la prosecretaria de informatica en pabellon argentina.

El proyecto se divide en dos módulos independientes que recopilan información diferente del datacenter.

---

## 🎯 Objetivo Macro del Proyecto

El **Monitoreo UPS** es un sistema automatizado de vigilancia en tiempo real de equipos de alimentación ininterrumpida (UPS) distribuidos en múltiples pisos de un datacenter. El sistema:

- **Recopila métricas** de 24+ UPS mediante protocolo SNMP (temperatura de batería, carga, autonomía, voltajes, corrientes)
- **Detecta anomalías** comparando lecturas contra umbrales configurables
- **Almacena historial** de errores en base de datos SQLite para evitar alertas duplicadas
- **Notifica automáticamente** al equipo técnico vía Google Chat cuando se detectan problemas o resoluciones
- **Exporta datos** en formato Telegraf/InfluxDB para visualización en Grafana
- **Ejecuta en paralelo** monitoreo de múltiples UPS para minimizar tiempo de ciclo

El sistema está diseñado para **reducir tiempo de respuesta** ante fallos de energía críticos y proporcionar **visibilidad centralizada** del estado de la infraestructura de energía.

---

## 📋 Requisitos Previos

### Software
- **Python**: 3.7 o superior
- **pip**: Gestor de paquetes de Python
- **Git**: Para clonar el repositorio (opcional)

### Acceso de Red
- **Conectividad SNMP** (puerto 161) a todos los UPS en dominio `.psi.unc.edu.ar`
- **Comunidad SNMP**: Credencial `publicapc` configurada en los UPS

### Configuración Requerida
- **Archivo `.env`**: Debe contener la URL del webhook de Google Chat:
  ```bash
  PASSWORDCHAT=https://chat.googleapis.com/v1/spaces/...
  ```
- **Acceso a base de datos**: Permisos para crear/escribir en directorio `./data/`
- **Permisos de logs**: Permisos para crear directorio `./logs/`

### Dependencias Python
Ver [requirements.txt](requirements.txt) para la lista completa. Las principales son:
- `easysnmp`: Comunicación SNMP
- `httplib2`: Envío de alertas vía webhook
- `python-dotenv`: Gestión de variables de entorno

---

## 🚀 Instalación

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/monitoreo-ups.git
cd monitoreo-ups
```

### Paso 2: Crear entorno virtual (recomendado)

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### Paso 3: Instalar dependencias

```bash
# Instalar desde requirements.txt
pip install -r requirements.txt
```

Verifica la instalación:
```bash
python -c "import easysnmp; print('✓ easysnmp instalado')"
python -c "import httplib2; print('✓ httplib2 instalado')"
```

### Paso 4: Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```bash
cat > .env << EOF
PASSWORDCHAT=https://chat.googleapis.com/v1/spaces/YOUR_WEBHOOK_URL
EOF
```

Reemplaza `YOUR_WEBHOOK_URL` con tu URL de webhook de Google Chat.

### Paso 5: Ajustar configuración (opcional)

Editar `src/config/configuracion.py` si es necesario:
- Cambiar hosts monitorados en `HOST_NAME_SHORT_F1`, `HOST_NAME_SHORT_F2`, `HOST_NAME_SHORT_F3`
- Ajustar umbrales de alerta (`VALOR_TEMP_BAT_MAX`, `VALOR_CARGA_MIN`, etc.)
- Modificar OIDs si se usan modelos de UPS diferentes

---

## 💡 Ejemplo Básico de Uso

### Ejecución Manual

```bash
# Activar entorno virtual (si no está activo)
source venv/bin/activate

# Ejecutar monitoreo una vez
cd /path/to/monitoreo-ups
python -m src.main

# Salida esperada:
# dc-ups,host=ups-dc autonomia=45.50
# ups_temp2,host=f1r2u1 battery=25,temp=22,capacity=95,load=35,life=15.50,current=5
# ups_temp2,host=f1r3u1 battery=24,temp=21,capacity=94,load=38,life=14.75,current=5
# ... (más líneas de Telegraf)
# 🔔 *Reporte de Estado: f1r2u1*
# ❌ [ADVERTENCIA] *TEMPERATURA_BATERIA_ALTA*: Valor actual *28 [°C]*
# (en Google Chat)
```

### Ejecución Automatizada (Cron)

Para ejecutar el monitoreo cada 5 minutos en Linux/Mac:

```bash
# Editar crontab
crontab -e

# Agregar línea (ejecutar cada 5 minutos)
*/5 * * * * cd /path/to/monitoreo-ups && source venv/bin/activate && python -m src.main >> logs/cron.log 2>&1
```

### Verificar Logs

```bash
# Ver logs de aplicación
tail -f logs/app.log

# Ver logs de errores
tail -f logs/errors.log

# Ver últimos eventos Telegraf
python -m src.main | grep "ups_temp2"
```

### Interpretación de Salida

```
# Formato Telegraf (para Grafana/InfluxDB)
ups_temp2,host=f1r2u1 battery=25,temp=22,capacity=95,load=35,life=15.50,current=5
           └─────┬─────┘ └──────────────────────────── valores ──────────────────────────┘
              tag                                    fields

# Ejemplo de alerta en Google Chat:
🔔 *Reporte de Estado: f1r2u1*
❌ [ADVERTENCIA] *TEMPERATURA_BATERIA_ALTA*: Valor actual *28 [°C]*
✅ [RESUELTO] CARGA_MINIMA volvió a la normalidad.
📅 *Fecha informe:* 13/05/2026 14:23:45
```

### Solución de Problemas Comunes

**Error: "SNMP timeout"**
```
→ Verificar conectividad de red: ping f1r2u1.psi.unc.edu.ar
→ Verificar comunidad SNMP en configuracion.py: COMMUNITY = "publicapc"
```

**Error: "URL de Google Chat no configurada"**
```
→ Asegurar .env existe y contiene PASSWORDCHAT=...
→ Verificar que el webhook URL es válido (comienza con https://chat.googleapis.com)
```

**No aparecen alertas en Google Chat**
```
→ Verificar logs: cat logs/errors.log
→ Probar conectividad: curl -X POST -H "Content-Type: application/json" \
    -d '{"text":"test"}' https://chat.googleapis.com/v1/spaces/...
```

---

## 📚 Documentación

Para documentación detallada sobre:
- **Configuración de Sphinx**: Ver [docs/GUIA_DOCUMENTACION.md](docs/GUIA_DOCUMENTACION.md)
- **API Reference**: Después de generar con Sphinx, abrir `docs/_build/html/index.html`
- **Arquitectura Técnica**: Ver [docs/arquitectura_y_uso.md](docs/arquitectura_y_uso.md)
- **Diagnóstico**: Ver [docs/DIAGNOSTICO.md](docs/DIAGNOSTICO.md)

---

## 📊 Arquitectura General del Sistema

```markdown
monitoreo-ups/
├── src/
│ ├── humedad_ups/ (Módulo 1: Monitoreo de humedad)
│ │ ├── constantes.py
│ │ └── main.py
│ └── state_ups/ (Módulo 2: Estado de UPS - POO)
│ ├── constantes.py
│ ├── main.py
│ ├── Sesiones.py (Clase UPS)
│ └── Validar_datos.py (Funciones de validación)
├── Makefile
└── README.md
```

---

## 1️⃣ MÓDULO: humedad_ups (Monitoreo de Humedad)

### Distribución de archivos

```markdown
humedad_ups/
├── constantes.py (Configuración SNMP)
└── main.py (Lógica principal)
```

### Funcionamiento

#### **constantes.py** - Configuración

Define los parámetros SNMP necesarios:

- `HOST_NAME`: Host del sensor de humedad (`f2r7u1.psi.unc.edu.ar`)
- `COMMUNITY`: Comunidad SNMP para autenticación (`publicapc`)
- `ODIH2`: OID que identifica el sensor de humedad (`1.3.6.1.4.1.318.1.1.25.1.2.1.7.2.1`)

#### **main.py** - Función principal

**`main()`** - Función que ejecuta el monitoreo:

1. Crea una sesión SNMP con el host definido en constantes
2. Realiza una consulta SNMP usando el OID de humedad (`ODIH2`)
3. Obtiene el valor de humedad actual del sensor
4. Extrae el nombre corto del host del FQDN
5. Imprime el resultado en formato compatible con **Grafana/InfluxDB**:

   ```bash
   ups_temp2,host={nombre} humidity={valor}
   ```

6. Maneja excepciones:
   - `EasySNMPTimeoutError`: Tiempo de espera agotado en conexión remota
   - Excepciones generales: Errores inesperados
   - En caso de error, termina el programa con `sys.exit(0)`

---

## 2️⃣ MÓDULO: state_ups (Monitoreo de Estado de UPS) - Programación Orientada a Objetos

### Distribución de archivos - state_ups

```markdown
state_ups/
├── constantes.py (Configuración, OIDs y umbrales)
├── main.py (Orquestador principal)
├── Sesiones.py (Clase UPS - Lógica POO)
├── Validar_datos.py (Funciones de validación)
├── Base_Datos.py (Gestión de SQLite - Almacenamiento de errores)
└── Error_State.py (Enum de tipos de errores)
```

---

### **Error_State.py** - Enum de tipos de errores

Define una enumeración con todos los tipos de errores posibles que puede generar un UPS:

```python
class Errores(Enum):
    TEMPERATURA_BATERIA_ALTA = 1    # Temperatura de batería excede umbral
    UIO_ROTO = 2                    # Sensor de temperatura ambiental desconectado
    UIO_TEMPERATURA_ALTA = 3        # Temperatura ambiente excede umbral
    CARGA_MINIMA = 4                # Carga de batería por debajo del umbral
    LOAD_MAXIMO = 5                 # Carga a la salida excede umbral
    AUTONOMIA_MINIMO = 6            # Tiempo de autonomía por debajo del umbral
```

Esta enumeración es utilizada por las funciones de validación y por la base de datos para mantener un registro consistente de los tipos de errores.

---

### **Base_Datos.py** - Gestión de SQLite

Implementa la clase `BaseDatos` para almacenar y gestionar el historial de errores en una base de datos SQLite. Permite evitar el reenvío duplicado de alertas y detectar cuando los errores se resuelven.

#### Estructura de la tabla `errores`

```sql
CREATE TABLE errores(
    id INTEGER PRIMARY KEY,
    ups_host TEXT NOT NULL,
    tipo_error TEXT NOT NULL,
    estado_error TEXT NOT NULL CHECK (estado_error IN ('activo', 'resuelto')),
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

#### Métodos principales

**1. `Crear_Base_datos()` - Inicialización**

- Crea la base de datos si no existe
- Inicializa la tabla `errores` con campos para ID, host, tipo de error, estado y timestamp

**2. `error_activo(ups_host, tipo_error)` - Consulta errores activos**

- Busca si existe un error activo específico para un UPS
- Retorna el registro si existe, `None` si no

**3. `error_resuelto(ups_host, tipo_error)` - Consulta errores resueltos**

- Busca si existe un registro resuelto para un determinado error
- Útil para verificar si un problema fue notificado anteriormente

**4. `agregar_error(ups_host, tipo_error)` - Registra nuevo error**

- Inserta un nuevo error con estado `'activo'` y timestamp actual
- Se llama cuando se detecta un error que no estaba registrado

**5. `resolver_error(ups_host, tipo_error)` - Resuelve errores**

- Cambia el estado de un error a `'resuelto'` y actualiza el timestamp
- Se llama cuando un error monitoreado vuelve a la normalidad

---

### **Sesiones.py** - Clase UPS (Núcleo POO)

#### Atributos de la clase

```python
hostname             # Nombre corto del UPS (ej: f1r2u1)
full_hostname        # HOSTNAME completo (ej: f1r2u1.psi.unc.edu.ar)
url                  # URL webhook para envío de alertas
session              # Objeto sesión SNMP
db                   # Instancia de BaseDatos para gestión de errores
temperatura_bateria  # Temperatura de la batería (°C)
temperatura_uio1     # Temperatura del sensor ambiental UIO (°C)
carga                # Porcentaje de carga de batería (%)
load                 # Porcentaje de carga de salida (%)
tiempo_autonomia     # Tiempo de autonomía en caso de fallo (minutos)
corriente            # Corriente suministrada por el UPS (Amperios)
```

#### Métodos de la clase

**1. `__init__(hostname, url, db_file)` - Constructor**

- Inicializa el hostname corto del UPS
- Construye el HOSTNAME completando con el dominio `.psi.unc.edu.ar`
- Almacena la URL del webhook para notificaciones
- **Crea instancia de `BaseDatos`** con el path especificado
- Crea la sesión SNMP usando la comunidad definida en constantes
- Llama automáticamente a `obtener_datos()` para recolectar métricas
- Imprime el estado actual en formato Grafana mediante `toString()`

**2. `obtener_datos()` - Recolección de métricas SNMP**
Realiza consultas SNMP al UPS para obtener:

- **Temperatura de batería** (`OIDB`): Convertida a entero
- **Temperatura UIO** (`OIDT` o `OIDTNEW`): Intenta con `OIDT` primero; si falla (firmware antiguo), usa `OIDTNEW`
- **Carga de batería** (`OIDCAPACITY`): Porcentaje actual
- **Carga de salida** (`OIDLOAD`): Porcentaje de carga conectada
- **Tiempo de autonomía** (`OIDLIFE`): Obtiene valor en decisegundos y lo convierte a minutos
- **Corriente** (`OIDCURRENT`): Amperios suministrados

Manejo de excepciones:

- `EasySNMPTimeoutError`: Timeout de conexión
- Excepciones genéricas: Otros errores SNMP
- Termina el programa al encontrar error

**3. `validar_datos()` - Validación inteligente de límites con persistencia**

Implementa un sistema de detección de errores con memoria que evita reenvío duplicado:

1. **Para cada validación**:
   - Invoca la función de validación correspondiente
   - Obtiene: `(error: Errores | None, mensaje: str)`

2. **Si se detecta un error** (`error is not None`):
   - **Consulta la BD**: ¿Existe este error activo para este UPS?
   - **Si NO existe**:
     - Registra el error en la BD con estado `'activo'`
     - Agrega el mensaje a la lista de notificaciones
   - **Si ya existe**:
     - NO genera mensaje (evita duplicados)
     - El error ya fue notificado en iteraciones anteriores

3. **Si NO hay error** (métrica dentro de rango normal):
   - **Consulta la BD**: ¿Existe registro de este error (activo o resuelto)?
   - **Si existe error activo**:
     - Marca el error como `'resuelto'` en la BD
     - Agrega mensaje de resolución: `[RESUELTO - host] métrica volvió a la normalidad`
   - **Si no existe o ya está resuelto**:
     - No genera mensaje (no hay cambio de estado)

4. **Envío de mensajes consolidados**:
   - Acumula todos los mensajes (alertas nuevas + resoluciones)
   - Si hay mensajes: los envía unidos por `\n` vía webhook
   - Si no hay cambios: no envía nada

**4. `envio_mensaje(msg)` - Notificación HTTP**

- Prepara headers HTTP con tipo `application/json`
- Crea objeto JSON: `{"text": "mensaje de alerta"}`
- Realiza POST request a la URL del webhook
- Permite notificaciones en plataformas como Slack, Teams, Google Chat, etc.

**5. `toString()` - Formato de salida Grafana**
Imprime todas las métricas en formato InfluxDB compatible:

```bash
ups_temp2,host={hostname} battery={temp_bat},temp={temp_uio},capacity={carga},load={load},life={autonomia},current={corriente}
```

Este formato es consumido directamente por Grafana para visualización

---

### **constantes.py** - Configuración Global

#### Listas de UPS a monitorear

```python
HOST_NAME_SHORT_F1  # Piso 1: f1r2u1, f1r3u1, f1r7u1, f1r9u1, f1r10u2, f1r11u1, f1r11u2
HOST_NAME_SHORT_F2  # Piso 2: 15 UPS (f2r1u1, f2r1u2, ..., f2r11u1, f2r11u2)
HOST_NAME_SHORT_F3  # Piso 3: f3r11u1, f3r11u2
HOST_NAME_SHORT     # Lista combinada
```

#### OIDs SNMP (Object Identifiers)

- `OIDB`: Temperatura de batería
- `OIDT`: Temperatura sensor UIO - firmware estándar
- `OIDTNEW`: Temperatura sensor UIO - firmware nuevo o defectuoso. Si el UPS no detecta el sensor de temperatura externo como un UIO, lo categoriza como algo externo, por eso hay dos OID.
- `OIDCAPACITY`: Carga de batería %
- `OIDLOAD`: Carga a la salida %
- `OIDLIFE`: Tiempo de autonomía en decisegundos
- `OIDCURRENT`: Corriente en Amperios
- `COMMUNITY`: Comunidad SNMP

#### Umbrales de alertas

| Métrica             | Umbral  | Condición |
| ------------------- | ------- | --------- |
| Temperatura batería | 27.0°C  | Máximo    |
| Temperatura UIO     | 27.0°C  | Máximo    |
| Carga batería       | 70.0%   | Mínimo    |
| Carga de salida     | 45.0%   | Máximo    |
| Tiempo autonomía    | 9.0 min | Mínimo    |

---

### **Validar_datos.py** - Funciones de validación

Cada función realiza una validación específica de una métrica del UPS y retorna una tupla `(error: Errores | None, mensaje: str)`.

Cada función también genera un mensaje de alerta descriptivo con el valor actual de la métrica.

### **main.py** - Orquestador Principal

#### Flujo de ejecución

1. **Limpieza de base de datos antigua**:
   - Función `borrar_si_vieja()` elimina la BD si tiene más de 10 minutos sin uso
   - Evita acumulación de archivos de BD innecesarios

2. Carga variables de entorno usando `dotenv` (cargar `PASSWORDCHAT` con URL webhook)

3. Inicializa lista vacía `ups_list` para almacenar objetos UPS

4. **Itera** sobre la lista de UPS definida en constantes:
   - Crea un objeto `UPS(host, url, db_file)` para cada equipo
   - Pasa la ruta de la BD centralizada (`const.DIR_DB`) a cada UPS
   - Agrega el objeto a la lista

5. Crea un `ThreadPoolExecutor` con máximo 6 workers (6 hilos simultáneos)

6. Para cada objeto UPS en la lista:
   - Envía `ups.validar_datos` al executor para ejecución paralela

7. El executor ejecuta validaciones de múltiples UPS concurrentemente

8. Cada UPS que tenga alertas nuevas o resoluciones las envía automáticamente vía webhook

---

### Dependencias de Python

```bash
easysnmp       # Comunicación SNMP
httplib2       # Solicitudes HTTP para webhooks
python-dotenv  # Carga de variables de entorno
```

### Configuración requerida

- Archivo `.env` en raíz del proyecto con: `PASSWORDCHAT=<URL_del_webhook>`
- Acceso SNMP a los UPS (puerto 161, comunidad `publicapc`)
- Conectividad de red a todos los equipos en dominio `psi.unc.edu.ar`
