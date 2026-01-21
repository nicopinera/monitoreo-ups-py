# Monitoreo UPS

La idea del presente proyecto es simplificar la monitorizacion de todos los ups que se encuentran dentro del data center de la prosecretaria de informatica en pabellon argentina.

El proyecto se divide en dos módulos independientes que recopilan información diferente del datacenter.

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
└── Validar_datos.py (Funciones de validación)
```

---

### **Sesiones.py** - Clase UPS (Núcleo POO)

#### Atributos de la clase

```python
hostname             # Nombre corto del UPS (ej: f1r2u1)
full_hostname        # HOSTNAME completo (ej: f1r2u1.psi.unc.edu.ar)
url                  # URL webhook para envío de alertas
session              # Objeto sesión SNMP
temperatura_bateria  # Temperatura de la batería (°C)
temperatura_uio1     # Temperatura del sensor ambiental UIO (°C)
carga                # Porcentaje de carga de batería (%)
load                 # Porcentaje de carga de salida (%)
tiempo_autonomia     # Tiempo de autonomía en caso de fallo (minutos)
corriente            # Corriente suministrada por el UPS (Amperios)
```

#### Métodos de la clase

**1. `__init__(hostname, url)` - Constructor**

- Inicializa el hostname corto del UPS
- Construye el HOSTNAME completando con el dominio `.psi.unc.edu.ar`
- Almacena la URL del webhook para notificaciones
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

**3. `validar_datos()` - Validación de límites**

- Invoca 5 funciones de validación independientes
- Cada función retorna una tupla `(válido, mensaje)`
- Recolecta todos los mensajes de alerta en una lista
- Si hay alertas, construye un mensaje final con todas ellas (separadas por `\n`)
- Envía el mensaje consolidado vía `envio_mensaje()`

**4. `envio_mensaje(msg)` - Notificación HTTP**

- Prepara headers HTTP con tipo `application/json`
- Crea objeto JSON: `{"text": "mensaje de alerta"}`
- Realiza POST request a la URL del webhook
- Permite notificaciones en plataformas como Slack, Teams, etc.

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

Cada función realiza una validación específica y retorna `(válido: bool, mensaje: str)`

---

### **main.py** - Orquestador Principal

#### Flujo de ejecución

1. Carga variables de entorno usando `dotenv` (cargar `PASSWORDCHAT` con URL webhook)
2. Inicializa lista vacía `ups_list` para almacenar objetos UPS
3. **Itera** sobre la lista de UPS definida en constantes:
   - Crea un objeto `UPS(host, url)` para cada equipo
   - Agrega el objeto a la lista
4. Crea un `ThreadPoolExecutor` con máximo 6 workers (6 hilos simultáneos)
5. Para cada objeto UPS en la lista:
   - Envía `ups.validar_datos` al executor para ejecución paralela
6. El executor ejecuta validaciones de múltiples UPS concurrentemente
7. Cada UPS que tenga alertas las envía automáticamente vía webhook

#### Ventajas del enfoque concurrente

- **Paralelismo**: 6 UPS se monitorean simultáneamente
- **Eficiencia**: Tiempo total = tiempo de 1 UPS × (24/6) = 4 ciclos en lugar de 24
- **No bloqueante**: Si un UPS tiene timeout, otros continúan

---

## 📈 Flujo General del Sistema

### Módulo humedad_ups (Simple - Procedural)

```markdown
Inicio
  ↓
Crear sesión SNMP
  ↓
Leer OID de humedad
  ↓
Imprimir valor (formato Grafana)
  ↓
Fin
```

### Módulo state_ups (Complejo - OOP + Concurrencia)

```markdown
Inicio
  ↓
Cargar URL webhook desde .env
  ↓
Para cada UPS (en paralelo - máx 6 simultáneos):
  ├─ Instanciar objeto UPS
  ├─ Constructor llama a obtener_datos()
  │   ├─ Conexión SNMP
  │   └─ Lectura 6 OIDs
  ├─ Imprime valores en formato Grafana
  ├─ Llama a validar_datos()
  │   ├─ Ejecuta 5 funciones de validación
  │   └─ Si hay alertas: envía JSON vía HTTP POST
  └─ Fin del objeto UPS
  ↓
Fin del executor (espera todos los threads)
```

---

## 🎯 Diseño Orientado a Objetos en state_ups

### Principios aplicados

✅ **Encapsulación**: Cada UPS es un objeto independiente con sus propios datos y métodos. Los atributos privados mantienen la integridad de la información.

✅ **Reutilización**: La clase `UPS` se instancia 24 veces sin repetir lógica. Un mismo patrón válido para cualquier número de equipos.

✅ **Escalabilidad**: Agregar nuevos UPS solo requiere modificar listas en `constantes.py`. La clase se adapta automáticamente.

✅ **Separación de responsabilidades**:

- `Sesiones.py`: Gestión del UPS y su comunicación SNMP
- `Validar_datos.py`: Lógica de validación independiente
- `constantes.py`: Configuración centralizada
- `main.py`: Orquestación y concurrencia

✅ **Concurrencia eficiente**: ThreadPoolExecutor permite monitorear múltiples UPS en paralelo sin bloqueos.

✅ **Mantenibilidad**: Cambios en validaciones solo afectan `Validar_datos.py`. Cambios en OIDs solo afectan `constantes.py`.

---

## 🔧 Requisitos del Sistema

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
