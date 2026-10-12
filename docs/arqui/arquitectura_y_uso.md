# Arquitectura del módulo de monitoreo UPS

Cómo está armado el código y cómo extenderlo. Para usarlo y operarlo, ver [monitoreo-ups.md](../monitoreo-ups.md); para la VM, el [runbook](../runbook_vm.md).

El código está separado en capas para que cada pieza cambie sin tocar las demás: las reglas de alerta no saben de Google Chat, los drivers no saben de la base de datos y el formato de los mensajes no sabe de SNMP.

1. [Una ejecución, de punta a punta](#una-ejecución-de-punta-a-punta)
2. [Capas](#capas)
3. [Ciclo de vida de una alerta](#ciclo-de-vida-de-una-alerta)
4. [Cómo extenderlo](#cómo-extenderlo)

## Una ejecución, de punta a punta

Telegraf ejecuta el programa una vez por minuto. Cada ejecución arranca, hace su trabajo y termina: no queda nada corriendo entre ejecuciones. Lo que tiene que recordarse (qué alertas ya se avisaron) vive en SQLite.

```text
main.iniciar()
 ├─ cargar_entorno()            .env + variables del proceso → Entorno (falla con código 1 si algo es inválido)
 ├─ configurar_logger()         data/logs/monitoreo.log
 └─ main(entorno)
     ├─ Notificador, RepositorioDB, GestorAlertas
     ├─ crear_tareas()          una tarea por equipo (28)
     ├─ ejecutar_tareas()       ThreadPoolExecutor: todas en paralelo
     │   └─ por equipo:  driver.ejecutar() → Lectura  →  gestor.procesar(lectura)
     ├─ escribir_lineas()       una sola escritura a stdout, desde el hilo principal
     └─ código de salida        0 si hubo al menos una métrica (si no, Telegraf descarta todo)
```

- **stdout es solo para Telegraf.** Cualquier otro texto rompe el parseo; los logs van al archivo ([logging.md](../logging.md)).
- **Un equipo que falla no frena a los demás.** Cada tarea está protegida: su error queda en el log y el resto de las métricas se publica igual. Un error al avisar (base o Google Chat) tampoco impide publicar las métricas de ese equipo.

## Capas

### `core/`: dominio

No importa nada de infraestructura (solo para las anotaciones de tipos).

- **[errores.py](../../src/core/errores.py):** el `Enum` `Errores`, el catálogo de alertas posibles. Su nombre es lo que se guarda en la base.
- **[alertas.py](../../src/core/alertas.py):**
  - `Regla(metrica, error, condicion, umbral, unidad)`: una alerta como dato. `condicion` es `"max"` (alerta si valor > umbral) o `"min"` (valor < umbral). Las reglas de los UPS están en `REGLAS_UPS` de [configuracion.py](../../src/config/configuracion.py) y se inyectan a los drivers.
  - `evaluar(reglas, datos)` → `Chequeo`s: una regla por métrica con dato. **Una métrica sin dato no se evalúa**, así no resuelve una alerta abierta.
  - `Equipo` (hostname, tipo para los mensajes, clave para la base y los hilos) y `Evento` (se abrió o se cerró un incidente; sin formato).
- **[ups_base.py](../../src/core/ups_base.py):** `BaseUPS`, el contrato de los drivers, y `Lectura`, lo que devuelve cada uno. `ejecutar()` no recibe argumentos y es igual para todos (método plantilla): lee (`obtener_datos`), arma las líneas (`lineas_telegraf`) y evalúa las reglas.
- **[gestor_alertas.py](../../src/core/gestor_alertas.py):** `GestorAlertas.procesar(lectura)` decide qué avisar, igual para cualquier equipo:
  - compara cada chequeo con los incidentes abiertos en la base y genera eventos `abrir`/`cerrar`;
  - `SIN_RESPUESTA_SNMP` se avisa recién después de `SNMP_FALLAS_PARA_ALERTA` ejecuciones seguidas sin respuesta (cuenta guardada en la base) y se resuelve con la primera respuesta;
  - avisa cada evento por separado y lo guarda **solo si el aviso salió**: si Google Chat falla, se detecta otra vez en la próxima ejecución (nunca se pierde una alerta).

### `drivers/`: un driver por tipo de equipo

Saben qué leer y cómo armar sus líneas. No usan la base ni el chat.

| Driver | Equipos | Línea de Telegraf | Reglas |
| --- | --- | --- | --- |
| [StateUPS](../../src/drivers/state_ups.py) | UPS APC de las filas 1–3 | `ups_temp2` | `REGLAS_UPS` |
| [DataCenterUPS](../../src/drivers/dc_ups.py) | UPS trifásico del DC | `dc-ups` (una línea por grupo) | ninguna (solo sin respuesta) |
| [HumedadUPS](../../src/drivers/hum_ups.py) | sensor de humedad de `f2r7u1` | `ups_temp2` | ninguna (solo sin respuesta) |

Detalles:

- `StateUPS` convierte la autonomía de TimeTicks (centésimas de segundo) a minutos y prueba dos OIDs para la temperatura ambiente, según el firmware (`OIDT`, si no `OIDTNEW`).
- `DataCenterUPS` calcula el promedio de corriente y las potencias por fase solo si están las tres fases (si no, darían un valor falsamente bajo).
- `HumedadUPS` usa la clave `f2r7u1-humedad`: el sensor vive en un UPS que también se monitorea, y así sus incidentes e hilos no se mezclan.
- Los nombres de las mediciones (`ups_temp2`, `dc-ups`) son los que usan los dashboards de Grafana: no cambiarlos sin coordinarlo.

### `infraestructura/`: el mundo exterior

- **[snmp_client.py](../../src/infraestructura/snmp_client.py):** `ClienteSNMP` (ezsnmp, SNMPv1). Devuelve números o `None`. Después del primer timeout no consulta más OIDs de ese host, así un UPS apagado no demora la ejecución.
- **[database.py](../../src/infraestructura/database.py) + [schema.sql](../../src/infraestructura/schema.sql):** SQLite en `data/errores-v2.db`. Tabla `incidentes` (una fila por incidente, con `inicio` y `fin`; abiertos = alertas activas, cerrados = historial) y `fallas_consecutivas`. Fechas en UTC.
- **[formato_chat.py](../../src/infraestructura/formato_chat.py):** arma la tarjeta (`cardsV2`) y el resumen de cada evento. Textos, colores, íconos y la clave del hilo (equipo + error + inicio) viven solo acá.
- **[notificador.py](../../src/infraestructura/notificador.py):** POST al webhook con `threadKey`, para que la resolución responda en el hilo de su alerta.
- **[logger.py](../../src/infraestructura/logger.py):** ver [logging.md](../logging.md).

### `config/`

- **[configuracion.py](../../src/config/configuracion.py):** lo que no depende del entorno: hosts, OIDs y reglas. Se cambia por Merge Request.
- **[entorno.py](../../src/config/entorno.py):** lo que sí (secretos, timeouts, rutas, nivel de log), desde el `.env` y las variables del proceso. Se valida todo junto al arrancar y se inyecta como `Entorno`: ningún otro módulo lee variables de entorno.

## Ciclo de vida de una alerta

Ejemplo: la carga de salida de `f1r11u1` supera el 60 %.

| Ejecución | Lectura | Base | Chat |
| --- | --- | --- | --- |
| 17:21 | load = 63 → en alerta | sin incidente abierto → se abre `(f1r11u1, LOAD_MAXIMO, inicio 20:21 UTC)` | tarjeta "Carga de salida alta · 63 % · máximo 60 %", hilo nuevo |
| 17:22 … 19:35 | sigue alta | incidente abierto: nada que hacer | nada |
| 19:36 | load = 48 → normal | se cierra con `fin 22:36 UTC` | respuesta en el hilo: "Carga de salida normalizada · 48 % · duró 2 h 15 min" |
| 21:00 | load = 65 | incidente **nuevo** (el anterior queda como historial) | tarjeta nueva, hilo nuevo |

Si en la ejecución de las 17:21 Google Chat no responde, el incidente no se abre y a las 17:22 se vuelve a detectar y a avisar.

## Cómo extenderlo

### Agregar un UPS APC

Agregar su hostname a la lista de su fila en [configuracion.py](../../src/config/configuracion.py) (`HOST_NAME_SHORT_F1/F2/F3`). Usa el mismo driver y las mismas reglas.

### Cambiar o agregar una alerta de los UPS APC

- **Cambiar un umbral:** editar su línea en `REGLAS_UPS`.
- **Alerta nueva sobre una métrica existente:** agregar el error a `Errores`, una `Regla` a `REGLAS_UPS` y sus textos a `TITULOS` en [formato_chat.py](../../src/infraestructura/formato_chat.py). Un test verifica que todo error tenga texto.

### Agregar alertas a otro equipo (por ejemplo, el UPS del DC)

Pasarle reglas al crear su driver en [main.py](../../src/main.py) (`_dc`): el gestor, la base y las tarjetas ya funcionan para cualquier equipo.

### Agregar un tipo de equipo nuevo

1. Sus OIDs en [configuracion.py](../../src/config/configuracion.py).
2. Un driver en `drivers/` que herede de `BaseUPS` e implemente `obtener_datos()` y `lineas_telegraf()`.
3. Una función que lo cree y su entrada en `crear_drivers()` de [main.py](../../src/main.py).
4. Tests en `tests/`, con `ClienteSNMPFalso` en lugar de la red.

### Cambiar el diseño de los mensajes

Solo [formato_chat.py](../../src/infraestructura/formato_chat.py). Para ver el resultado sin esperar una alerta real: `make probar-tarjetas WEBHOOK='<webhook de prueba>'`.
