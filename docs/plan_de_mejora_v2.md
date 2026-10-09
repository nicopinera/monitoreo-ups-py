# Plan de mejora v2 — Monitoreo UPS

> Fecha de revisión: 2026-10-09 · Rama revisada: `dev` (commit `4637f98`)

Este documento junta tres cosas:

1. Los **problemas encontrados** al revisar todo el código (bugs, riesgos y deuda técnica), priorizados.
2. La **modernización del proyecto**: migración a `uv`, `pyproject.toml` completo y CI con `ruff`, `mypy`, `pip-audit`, tests y cobertura.
3. El **nuevo esquema de despliegue**: imagen Docker que Telegraf ejecuta con `docker run`, y un cron en la VM que trae `main`, construye la imagen y limpia las imágenes viejas (la instancia de GitLab no tiene Container Registry).

---

## Índice

1. [Situación actual](#1-situación-actual)
2. [Hallazgos de la revisión de código](#2-hallazgos-de-la-revisión-de-código)
   - [Resumen priorizado](#21-resumen-priorizado)
   - [Prioridad alta](#22-prioridad-alta)
   - [Prioridad media](#23-prioridad-media)
   - [Prioridad baja / deuda técnica](#24-prioridad-baja--deuda-técnica)
3. [Migración a uv y pyproject.toml](#3-migración-a-uv-y-pyprojecttoml)
4. [CI/CD: calidad y seguridad](#4-cicd-calidad-y-seguridad)
5. [Contenerización](#5-contenerización)
6. [Despliegue automático con cron en la VM](#6-despliegue-automático-con-cron-en-la-vm)
7. [Hoja de ruta por fases](#7-hoja-de-ruta-por-fases)
8. [Preguntas abiertas](#8-preguntas-abiertas)

---

## 1. Situación actual

```text
Telegraf (VM) ──exec cada X s──▶ python3 src/main.py (repo clonado en la VM)
                                   │
                                   ├─ SNMP ─▶ 26 UPS APC + UPS trifásico del DC + sensor de humedad
                                   ├─ SQLite data/errores.db (estado de alertas, dentro del repo)
                                   ├─ Google Chat (webhook en .env, dentro del repo)
                                   ├─ Seq http://localhost:5341 (logs, vía seqlog; se elimina en v2)
                                   └─ stdout (line protocol) ─▶ Telegraf ─▶ InfluxDB
```

**Problema de operación:** cada cambio en el repo obliga a entrar a la VM, actualizar el clon a mano, resolver conflictos y verificar que vuelva a correr. Las dependencias se instalan con `apt` (`Makefile`), así que la VM y el CI no usan las mismas versiones.

**Estado del código verificado en esta revisión:**

| Verificación                                  | Resultado                                                                                                                           |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `pytest` (local)                              | 17 tests pasan; sólo cubren `core/validacion.py` y `infraestructura/database.py`. `test_main.py` es un placeholder (`assert 5==5`). |
| `ruff check` (reglas E, F, W, B, UP, SIM, PL) | 188 hallazgos, 92 autocorregibles (`F403/F405` por `import *`, `E711` por `== None`, imports sin usar, etc.).                       |
| CI (`.gitlab-ci.yml`)                         | Probablemente nunca corrió los tests (ver [A7](#a7-el-ci-no-ejecuta-realmente-los-tests)).                                          |

---

## 2. Hallazgos de la revisión de código

### 2.1 Resumen priorizado

| ID                                                                         | Prioridad | Problema                                                          | Archivo                                                                                                                     |
| -------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [A1](#a1-si-falla-snmp-se-publican-ceros-y-se-disparan-alertas-falsas)     | Alta      | Si falla SNMP, se publican ceros y se disparan alertas falsas     | [state_ups.py](../src/drivers/state_ups.py#L17-L40), [dc_ups.py](../src/drivers/dc_ups.py#L24)                              |
| [A2](#a2-un-error-en-el-ups-del-dc-o-en-humedad-aborta-todo-el-monitoreo)  | Alta      | Un error en el UPS del DC o en humedad aborta todo el monitoreo   | [main.py](../src/main.py#L50-L51)                                                                                           |
| [A3](#a3-valores-no-numéricos-rompen-el-line-protocol)                     | Alta      | Valores no numéricos rompen el line protocol                      | [state_ups.py](../src/drivers/state_ups.py#L33), [hum_ups.py](../src/drivers/hum_ups.py#L11)                                |
| [A4](#a4-el-fallback-oidt--oidtnew-no-funciona-en-todos-los-casos)         | Alta      | El fallback `OIDT → OIDTNEW` no funciona en todos los casos       | [state_ups.py](../src/drivers/state_ups.py#L37-L40)                                                                         |
| [A5](#a5-no-hay-timeouts-acotados-snmp-y-google-chat)                      | Alta      | No hay timeouts acotados (SNMP y Google Chat)                     | [snmp_client.py](../src/infraestructura/snmp_client.py#L8), [notificador.py](../src/infraestructura/notificador.py#L24-L26) |
| [A6](#a6-el-estado-y-los-secretos-viven-dentro-del-repo)                   | Alta      | El estado (SQLite) y los secretos (`.env`) viven dentro del repo  | [configuracion.py](../src/config/configuracion.py#L90-L93)                                                                  |
| [A7](#a7-el-ci-no-ejecuta-realmente-los-tests)                             | Alta      | El CI no ejecuta realmente los tests                              | [.gitlab-ci.yml](../.gitlab-ci.yml#L14-L18)                                                                                 |
| [A8](#a8-si-falla-el-envío-a-google-chat-la-alerta-se-pierde-para-siempre) | Alta      | Si falla el envío a Google Chat, la alerta se pierde para siempre | [state_ups.py](../src/drivers/state_ups.py#L50-L64)                                                                         |
| [M1](#m1-eliminar-seqlog-y-pasar-a-logging-estándar)                       | Media     | Eliminar seqlog y pasar a `logging` estándar a stderr             | [logger.py](../src/infraestructura/logger.py)                                                                               |
| [M2](#m2-salida-a-stdout-desde-varios-hilos)                               | Media     | Varios hilos escriben a stdout a la vez                           | [state_ups.py](../src/drivers/state_ups.py#L105)                                                                            |
| [M3](#m3-el-ups-trifásico-del-dc-no-tiene-alertas)                         | Media     | El UPS trifásico del DC no tiene alertas                          | [dc_ups.py](../src/drivers/dc_ups.py#L41-L43)                                                                               |
| [M4](#m4-el-contrato-baseups-no-se-respeta)                                | Media     | El contrato `BaseUPS` no se respeta                               | [ups_base.py](../src/core/ups_base.py)                                                                                      |
| [M5](#m5-modelo-de-datos-de-sqlite)                                        | Media     | Modelo de datos de SQLite y manejo de conexiones                  | [database.py](../src/infraestructura/database.py)                                                                           |
| [M6](#m6-dominio-acoplado-a-la-presentación-y-a-strings-mágicos)           | Media     | Dominio acoplado a la presentación y a strings mágicos            | [validacion.py](../src/core/validacion.py), [state_ups.py](../src/drivers/state_ups.py#L70-L94)                             |
| [M7](#m7-configuración-y-secretos-hardcodeados)                            | Media     | Configuración y secretos en el código                             | [configuracion.py](../src/config/configuracion.py)                                                                          |
| [M8](#m8-threadpoolexecutor-sin-control-de-resultados)                     | Media     | `ThreadPoolExecutor` sin control de resultados                    | [main.py](../src/main.py#L53-L55)                                                                                           |
| [M9](#m9-easysnmp-sin-mantenimiento)                                       | Media     | `easysnmp` sin mantenimiento                                      | —                                                                                                                           |
| [B1–B10](#24-prioridad-baja--deuda-técnica)                                | Baja      | Estilo, layout del paquete, tests, documentación desactualizada   | varios                                                                                                                      |

### 2.2 Prioridad alta

#### A1. Si falla SNMP, se publican ceros y se disparan alertas falsas

**Dónde:** [state_ups.py:17-24](../src/drivers/state_ups.py#L17-L24), [state_ups.py:35](../src/drivers/state_ups.py#L35), [state_ups.py:40](../src/drivers/state_ups.py#L40), [dc_ups.py:24](../src/drivers/dc_ups.py#L24), [hum_ups.py:15-16](../src/drivers/hum_ups.py#L15-L16)

Todos los drivers inicializan las métricas en `0` y las dejan así si la consulta falla. Si un UPS no responde (apagado, sin red, timeout):

- Se imprime `capacity=0, life=0, load=0, ...` y **en Grafana aparece un dato falso** (una caída a cero, no un hueco).
- `validar_carga(0)` y `validar_tiempo_autonomia(0)` dan error, así que **llegan alertas `CARGA_MINIMA` y `AUTONOMIA_MINIMO` falsas** a Google Chat. El problema real (el UPS no responde) no se informa.
- Con la temperatura en `0`, `UIO_ROTO` (que exige `< 0`) nunca se detecta.

**Propuesta:**

- Representar "sin dato" con `None`, nunca con `0`.
- No imprimir los campos sin dato. Si no hay ningún dato, no imprimir la línea de ese UPS o imprimir un campo explícito `snmp_ok=0i`.
- No validar umbrales sobre métricas sin dato.
- Agregar un error de dominio `SIN_RESPUESTA_SNMP` que se notifique una sola vez y se resuelva cuando el equipo vuelva a responder, con la misma lógica de la base de datos.

#### A2. Un error en el UPS del DC o en humedad aborta todo el monitoreo

**Dónde:** [main.py:50-51](../src/main.py#L50-L51), [dc_ups.py:20-22](../src/drivers/dc_ups.py#L20-L22)

`humedad_driver.ejecutar()` y `dc_driver.ejecutar()` corren **antes** que los 26 UPS y fuera de cualquier `try`. En `DataCenterUPS.obtener_datos`, `int(valor_raw)` lanza `ValueError` si el agente devuelve algo no numérico (por ejemplo `NOSUCHINSTANCE`). Esa excepción llega a `__main__`, que hace `raise`:

- No se monitorea ningún UPS de state, así que no hay métricas ni alertas.
- El proceso termina con código ≠ 0. Telegraf `inputs.exec` trata eso como error y **descarta toda la salida de esa ejecución**, incluida la línea de humedad que ya se había impreso.

**Propuesta:** aislar cada driver en su propio `try/except`, como ya se hace en `StateUPS.ejecutar`. Que `main` siempre termine con código 0 si se pudo emitir al menos una métrica, y registrar en el log (stderr) cada driver que falle.

#### A3. Valores no numéricos rompen el line protocol

**Dónde:** [state_ups.py:33](../src/drivers/state_ups.py#L33), [hum_ups.py:11](../src/drivers/hum_ups.py#L11), [hum_ups.py:19](../src/drivers/hum_ups.py#L19)

`StateUPS` guarda el valor crudo de SNMP (un `str`) para todo lo que no es `life`, y `HumedadUPS` imprime el valor tal cual llega. Si el agente responde `NOSUCHOBJECT`, `NOSUCHINSTANCE` o un string vacío, se imprime algo como:

```text
ups_temp2,host=f1r2u1 battery=NOSUCHINSTANCE,temp=0,...
```

Esa línea es inválida en line protocol porque un string sin comillas no es un valor válido. Según la versión del parser de Telegraf, se pierde esa línea o **toda la salida de esa ejecución**. Además, `float(valor)` en las validaciones lanza `ValueError` después de haber impreso la línea, así que el UPS queda sin validar.

**Propuesta:**

- Que `ClienteSNMP` devuelva `float | None`: parsear y validar en la capa de infraestructura.
- Crear un helper único `formatear_linea(measurement, tags, fields)` que omita los `None`, escape tags y valide tipos. Los drivers devuelven `dict` y el formateo queda en un solo lugar.

#### A4. El fallback `OIDT → OIDTNEW` no funciona en todos los casos

**Dónde:** [state_ups.py:37-40](../src/drivers/state_ups.py#L37-L40), [snmp_client.py:11-20](../src/infraestructura/snmp_client.py#L11-L20)

El fallback a `OIDTNEW` sólo ocurre cuando `obtener_valor` devuelve `None`, y eso sólo pasa **si hubo una excepción**. Si el agente responde "no existe ese OID" (en SNMPv2c, easysnmp devuelve un `SNMPVariable` con `value='NOSUCHOBJECT'` o `'NOSUCHINSTANCE'` sin lanzar excepción), entonces:

1. `temp_val` es un string, así que no se intenta `OIDTNEW`.
2. `int('NOSUCHINSTANCE')` lanza `ValueError` y aborta todo `obtener_datos` de ese UPS, que se queda **sin métricas**.

Con SNMPv1 (el valor actual de `VERSION_SNMP`) el comportamiento depende de cómo easysnmp traduzca el `noSuchName`. Hay que **verificarlo contra un UPS con firmware viejo**.

**Propuesta:** en `ClienteSNMP.obtener_valor`, revisar `snmp_type` y devolver `None` si es `NOSUCHOBJECT`, `NOSUCHINSTANCE` o `ENDOFMIBVIEW`. Alternativa: crear la `Session` con `abort_on_nonexistent=True` y capturar `EasySNMPNoSuchObjectError` y `EasySNMPNoSuchInstanceError`.

#### A5. No hay timeouts acotados (SNMP y Google Chat)

**Dónde:** [snmp_client.py:8](../src/infraestructura/snmp_client.py#L8), [notificador.py:24-26](../src/infraestructura/notificador.py#L24-L26)

- La `Session` de easysnmp usa los valores por defecto de net-snmp: timeout de alrededor de 1 s y 3 reintentos. Un UPS caído cuesta unos 4 s **por OID**, y `StateUPS` consulta hasta 7 OIDs. Son casi 30 s por UPS caído, con sólo 6 workers para 26 equipos.
- `httplib2.Http()` se crea **sin timeout**. Si Google Chat no responde, el hilo queda colgado indefinidamente.
- `time.sleep(1)` antes de cada envío suma latencia sin un motivo claro.

Telegraf corta el comando al llegar a su `timeout` (5 s por defecto en `inputs.exec`), y en ese caso **se pierde toda la ejecución**.

**Propuesta:**

- `Session(..., timeout=1, retries=1)`, configurable por variable de entorno.
- Cortar la consulta de un host después del primer timeout: si no respondió el primer OID, no seguir con los demás.
- `Http(timeout=10)`, o reemplazar httplib2 por `requests` (o por `urllib.request` de la librería estándar para no sumar dependencias) con timeout explícito.
- Medir la duración total de la ejecución y ajustar `timeout` e `interval` de Telegraf con margen (ver [§5.4](#54-ejecución-desde-telegraf)).
- Subir `max_workers` (por ejemplo a 13) y hacerlo configurable.

#### A6. El estado y los secretos viven dentro del repo

**Dónde:** [configuracion.py:90-93](../src/config/configuracion.py#L90-L93)

`ARCHIVO_DB` (`data/errores.db`) y `ARCHIVO_ENV` (`.env`) se calculan relativos a la raíz del repo clonado. Esto:

- Probablemente es parte del origen de los **conflictos al actualizar la VM**: hay archivos generados y editados a mano dentro del árbol de git.
- **Con Docker es crítico:** si la base no se monta como volumen, cada `docker run` arranca con una base vacía. Cada error activo se tomaría como nuevo **y se notificaría en cada ejecución**, llenando el chat.

**Propuesta:** leer las rutas de variables de entorno (`MONITOREO_DATA_DIR`, por defecto `/data` en el contenedor). Mover el estado a `/var/lib/monitoreo-ups/` en la VM y los secretos a `/etc/monitoreo-ups/monitoreo.env`, ambos fuera del clon (ver [§5](#5-contenerización)). Empaquetar el script SQL dentro del paquete y leerlo con `importlib.resources`.

#### A7. El CI no ejecuta realmente los tests

**Dónde:** [.gitlab-ci.yml:14-18](../.gitlab-ci.yml#L14-L18), [Makefile:36-38](../Makefile#L36-L38)

`make install_dependencias_ci` instala pytest **dentro de `venv/`**, pero el job ejecuta `pytest` del `PATH` del sistema. La imagen `python:3.9` no trae pytest, así que el job debería fallar con `pytest: command not found`. Hay que **confirmarlo en el historial de pipelines**. Además:

- Python 3.9 llegó a fin de vida en octubre de 2025.
- El pipeline sólo corre en merge requests, no en `main`.
- No hay lint, tipado, auditoría de dependencias ni cobertura.

**Propuesta:** reemplazarlo por completo con el pipeline de la [§4](#4-cicd-calidad-y-seguridad).

#### A8. Si falla el envío a Google Chat, la alerta se pierde para siempre

**Dónde:** [state_ups.py:50-64](../src/drivers/state_ups.py#L50-L64), [state_ups.py:96-101](../src/drivers/state_ups.py#L96-L101), [notificador.py:34-37](../src/infraestructura/notificador.py#L34-L37)

`_gestionar_error_db` marca el error como `activo` en la base **antes** de enviar la notificación. Si el webhook falla (por red, un 5xx o el timeout de A5), `enviar_mensajes` sólo registra el error. En la siguiente ejecución el error ya figura como activo y **no se vuelve a notificar**. Lo mismo pasa con los mensajes de "resuelto".

Además, si `notificador` es `None` (el valor por defecto del constructor), [state_ups.py:101](../src/drivers/state_ups.py#L101) lanza `AttributeError`.

**Propuesta:** que `enviar_mensajes` devuelva `bool` y persistir el cambio de estado **sólo si el envío fue exitoso**, o agregar una columna `notificado` y reintentar los pendientes en cada ejecución. Usar un notificador "nulo" (Null Object) en lugar de `None`.

### 2.3 Prioridad media

#### M1. Eliminar seqlog y pasar a `logging` estándar

**Dónde:** [logger.py](../src/infraestructura/logger.py), [main.py:15-17](../src/main.py#L15-L17), [snmp_client.py](../src/infraestructura/snmp_client.py), [notificador.py](../src/infraestructura/notificador.py), [state_ups.py](../src/drivers/state_ups.py)

**Decisión:** Seq no se usa, así que se **elimina `seqlog`** del proyecto y se pasa al módulo `logging` de la librería estándar, escribiendo a **stderr**. En el esquema con Docker, stderr lo captura Telegraf (que lo muestra en su propio log cuando el comando falla), y también queda disponible para `journalctl`/`docker logs` si se corre a mano. stdout queda reservado exclusivamente para line protocol.

Problemas del código actual que esto resuelve o que hay que corregir en el cambio:

- `configurar_logger()` intenta mandar todo a `http://localhost:5341` en cada ejecución ([logger.py:22-28](../src/infraestructura/logger.py#L22-L28)), con `batch_size=1`: un POST HTTP por log hacia un servicio que no se usa. Si nada escucha en ese puerto, los logs se pierden (y dentro de un contenedor `localhost` ni siquiera es la VM).
- Se configura **al importar** `main.py` ([main.py:16](../src/main.py#L16)). Hay que moverlo dentro de `run()`.
- Los logs pasan kwargs propios de seqlog (`host=..., oid=...` en [snmp_client.py:16](../src/infraestructura/snmp_client.py#L16), [snmp_client.py:19](../src/infraestructura/snmp_client.py#L19), [notificador.py:35](../src/infraestructura/notificador.py#L35) y [state_ups.py:113](../src/drivers/state_ups.py#L113)). **Con `logging` estándar esas llamadas lanzan `TypeError`**, así que al quitar seqlog hay que reescribirlas sí o sí; si no, un error manejado (timeout SNMP, fallo del webhook) pasa a ser una excepción nueva dentro del `except`. Hoy ya pasa en los tests o con cualquier logger creado antes de `log_to_seq`.
- Usar formato perezoso de `logging` en lugar de f-strings: `logger.warning("Timeout SNMP en %s (oid=%s)", host, oid)`. Ruff lo verifica con las reglas `G` y `LOG` (§3.3).
- Código y documentación muertos: `RotatingFileHandler` importado sin uso, `LOGS_DIR`, `APP_LOG_FILE` y `ERROR_LOG_FILE` sin uso, y [docs/logger/Mejoras.md](logger/Mejoras.md) describe archivos rotados y un logger `telegraf` que **no existen**. No hace falta escribir archivos de log dentro del contenedor (es efímero): borrar esas constantes y actualizar o archivar ese documento.
- `warnings.filterwarnings("ignore", category=UserWarning)` ([main.py:15](../src/main.py#L15)) silencia todos los `UserWarning` del proceso. Si hace falta, filtrar sólo el módulo que los genera.

**Propuesta de `logger.py`:**

```python
import logging
import os
import sys


def configurar_logger() -> None:
    """Logs a stderr; stdout queda reservado para line protocol."""
    nivel = os.getenv("LOG_LEVEL", "WARNING").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s")
    )
    logging.basicConfig(level=nivel, handlers=[handler], force=True)
```

Nivel por defecto `WARNING`: en una ejecución normal no se escribe nada, y lo que aparezca en stderr es algo para mirar. Pasos del cambio: `uv remove seqlog`, reescribir las llamadas con kwargs y borrar `set_global_log_properties`/`log_to_seq`.

#### M2. Salida a stdout desde varios hilos

**Dónde:** [state_ups.py:105](../src/drivers/state_ups.py#L105)

Los `StateUPS` corren en 6 hilos y cada uno hace `print()`. En CPython, `print` hace **dos escrituras** (el texto y después el `\n`), así que dos hilos pueden intercalarse y producir `lineaAlineaB\n\n`, que es inválido para Telegraf. Es poco frecuente, pero cuando pasa se pierde la ejecución entera.

**Propuesta:** que `ejecutar()` **devuelva** las líneas (o un `dict` de métricas) y que `main` las imprima desde el hilo principal con un único `sys.stdout.write("\n".join(lineas) + "\n")`. Esto además facilita testear los drivers.

#### M3. El UPS trifásico del DC no tiene alertas

**Dónde:** [dc_ups.py:41-43](../src/drivers/dc_ups.py#L41-L43)

`DataCenterUPS.validar_datos_y_notificar` es un `pass` y el driver se crea sin notificador ni base de datos. Es, probablemente, el UPS más crítico del datacenter y es el único sin alertas.

**Propuesta:** definir umbrales para autonomía, carga de batería, temperatura de batería, carga de salida, desbalance de corriente entre fases y tensión de entrada fuera de rango. Reutilizar la misma lógica de base de datos y notificación (ver M4 y M6).

Observaciones menores del mismo archivo:

- `OID_VOLTAJE_OUT` y `OID_V_OUT_AN` son el mismo OID, así que se consulta dos veces lo mismo.
- `corriente_prom` promedia ceros cuando falla una fase (ver A1).
- `potencia_w_out` usa un `FP_OUT` fijo de 0,95. Si el equipo expone potencia activa por OID, conviene leerla directamente.

#### M4. El contrato `BaseUPS` no se respeta

**Dónde:** [ups_base.py](../src/core/ups_base.py), drivers

La clase abstracta define `obtener_datos(self)` y `ejecutar(self)`, pero cada driver los sobrescribe con firmas distintas: `obtener_datos(self, oid_metricas)`, `obtener_datos(self, oid_dicc, oidtemp, oidtemp2)`, etc. Esto viola el principio de sustitución de Liskov, `mypy` lo va a marcar (`incompatible override`) y obliga a `main` a conocer los parámetros de cada driver, que es justo lo que la interfaz debería esconder. Además, `HumedadUPS.validar_datos_y_notificar` no valida nada: sólo normaliza `None` a `0`.

**Propuesta:**

```python
class BaseUPS(ABC):
    def __init__(self, hostname: str, cliente: ClienteSNMP, oids: Mapping[str, str], ...) -> None: ...

    @abstractmethod
    def obtener_datos(self) -> dict[str, float | None]: ...

    @abstractmethod
    def validar(self, datos: dict[str, float | None]) -> list[Alerta]: ...

    def ejecutar(self) -> ResultadoEjecucion:  # método plantilla, común a todos
        datos = self.obtener_datos()
        alertas = self.validar(datos)
        return ResultadoEjecucion(lineas=..., alertas=alertas)
```

`main` pasa a recorrer una lista homogénea de drivers y llama a `d.ejecutar()` sin argumentos.

#### M5. Modelo de datos de SQLite

**Dónde:** [database.py](../src/infraestructura/database.py), [creacion_tabla_state.sql](../data/creacion_tabla_state.sql)

- Por cómo se usa, **nunca hay más de una fila por (host, tipo_error)**: `agregar_error` sólo se llama si no hay ninguna fila, y después `activar_error` y `resolver_error` modifican esa misma fila y pisan `fecha`. En la práctica es una **tabla de estado**, no un historial. Hay que elegir uno de los dos modelos:
  - **Estado:** `UNIQUE(ups_host, tipo_error)` + `INSERT ... ON CONFLICT DO UPDATE`. Las cinco funciones se reducen a `obtener_estado()` y `guardar_estado()`.
  - **Historial:** insertar una fila nueva por cada transición y consultar la última.
- No hay índice sobre `(ups_host, tipo_error, estado_error)`.
- `with sqlite3.connect(...) as conn` **no cierra la conexión**: el context manager de sqlite3 sólo hace commit o rollback. Hay que cerrarla de forma explícita o usar `contextlib.closing`.
- Si dos procesos se pisan (una ejecución de Telegraf que se superpone con otra o con una corrida manual), SQLite puede devolver `database is locked`. Configurar `timeout=10` en `connect` y `PRAGMA journal_mode=WAL`.
- El comentario de [state_ups.py:63](../src/drivers/state_ups.py#L63) dice "Se marca como activo" cuando en realidad se resuelve.

#### M6. Dominio acoplado a la presentación y a strings mágicos

**Dónde:** [validacion.py](../src/core/validacion.py), [state_ups.py:70-94](../src/drivers/state_ups.py#L70-L94)

- Las funciones de validación del **dominio** arman mensajes con formato de Google Chat (`*negrita*`). El formato del mensaje le corresponde al notificador.
- Las cinco funciones de validación son casi idénticas y leen umbrales globales de `config`. Se pueden reemplazar por una tabla declarativa de reglas, del tipo `Regla(metrica="load", operador=">", umbral=60, error=Errores.LOAD_MAXIMO, unidad="%")`, con los umbrales inyectados. Así son fáciles de testear y de reutilizar en el DC (M3).
- `state_ups.py` usa los nombres de error como strings literales (`"TEMPERATURA_BATERIA_ALTA"`, `"UIO_ROTO"`, etc.) en lugar del `Enum`. Si se renombra un miembro de `Errores`, nada lo detecta.
- El manejo de `UIO_ROTO` y `UIO_TEMPERATURA_ALTA` ([state_ups.py:77-82](../src/drivers/state_ups.py#L77-L82)) es difícil de leer. Con reglas independientes por error se simplifica.
- `from core.validacion import *` ([state_ups.py:4](../src/drivers/state_ups.py#L4)) trae `Errores` de forma implícita. Ruff lo marca 20 veces (F403/F405).

#### M7. Configuración y secretos hardcodeados

**Dónde:** [configuracion.py](../src/config/configuracion.py)

- La comunidad SNMP (`COMMUNITY = "publicapc"`) está en el código y versionada en git. Es una credencial: debe ir a variables de entorno.
- La variable `PASSWORDCHAT` contiene una **URL de webhook**. Conviene renombrarla a `GOOGLE_CHAT_WEBHOOK_URL` y actualizar [.env.example](../.env.example).
- Hay un comentario residual `# ,'f2r9u1'` ([configuracion.py:9](../src/config/configuracion.py#L9)) cuando `f2r9u1` ya está en la lista.
- Los umbrales están documentados con valores distintos en distintos lugares: el README dice 27 °C y el código 28; el commit `480f293` dice 50 % y el código actual tiene 60. Conviene que haya **una sola fuente de verdad** (el código o un archivo de configuración) y que el README remita a ella.
- Con Docker, cambiar un host o un umbral implica commit, build y deploy, algo aceptable gracias al cron (§6). Los **secretos** y los valores que dependen del entorno (rutas, timeouts, nivel de log) deben venir de `--env-file`.

#### M8. `ThreadPoolExecutor` sin control de resultados

**Dónde:** [main.py:53-55](../src/main.py#L53-L55)

Los `Future` de `executor.submit` se descartan: cualquier excepción que escape del `try` de `StateUPS.ejecutar` se pierde sin registrarse. Hay que guardar los futures, iterar con `as_completed` y registrar los fallos. Esto encaja con M2: cada future devuelve sus líneas.

#### M9. `easysnmp` sin mantenimiento

`easysnmp` (0.2.6) no tiene releases desde hace años, es una extensión en C que necesita `libsnmp-dev` para compilarse y en la VM se instala desde `apt` (`python3-easysnmp`). En una imagen Docker con un Python más nuevo, la compilación puede fallar.

**Propuesta:** en el primer build de la imagen, validar que compila contra `python:3.12-slim-bookworm`. A mediano plazo, evaluar `ezsnmp` (un fork mantenido con API casi idéntica) o `pysnmp` (Python puro, sin dependencias de C). Como `ClienteSNMP` ya aísla la librería, el cambio queda contenido en un solo archivo.

### 2.4 Prioridad baja / deuda técnica

| ID  | Problema                                                                                                                                                                                                                                                                                  | Propuesta                                                                                                                                                |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B1  | Los paquetes de primer nivel se llaman `config`, `core`, `drivers` e `infraestructura`: nombres genéricos que pueden chocar con otras librerías. Los tests importan `src.core...` mientras el código importa `core...`, así que el mismo módulo se carga dos veces con nombres distintos. | Reestructurar como `src/monitoreo_ups/{config,core,drivers,infraestructura}` y usar imports absolutos `monitoreo_ups.…` (ver §3).                        |
| B2  | La carpeta [scrip/](../scrip/) tiene pruebas sueltas (`loggerv1.py` está vacío).                                                                                                                                                                                                          | Eliminarla.                                                                                                                                              |
| B3  | [test_main.py](../test/test_main.py) es un placeholder. No hay tests de drivers, notificador, cliente SNMP ni del flujo de `main`.                                                                                                                                                        | Tests de drivers con un `ClienteSNMP` falso (fake), del notificador con `responses`/mocks y del formateo de line protocol. Renombrar `test/` a `tests/`. |
| B4  | Las comparaciones `== None` / `!= None` aparecen en [hum_ups.py:15](../src/drivers/hum_ups.py#L15) y en los tests.                                                                                                                                                                        | `is None` (`ruff --fix`).                                                                                                                                |
| B5  | Faltan type hints en todo el proyecto.                                                                                                                                                                                                                                                    | Agregarlos de forma progresiva, con `mypy` en el CI (§4).                                                                                                |
| B6  | El [Makefile](../Makefile) instala con `sudo apt`, `run_hum` y `run_state` son idénticos.                                                                                                                                                                                                 | Reemplazarlo por objetivos basados en `uv`: `make lint`, `make test`, `make build`, `make run`.                                                          |
| B7  | Los shebangs `#!/usr/bin/python3` en todos los módulos y el `chmod +x` del Makefile ya no hacen falta.                                                                                                                                                                                    | Usar el entry point `monitoreo-ups` del `pyproject.toml`.                                                                                                |
| B8  | El [README.md](../README.md) describe una estructura vieja (`humedad_ups/`, `state_ups/`, `Sesiones.py`, `borrar_si_vieja()`) que ya no existe. Dice "decisegundos" para `life`, pero la división por 6000 corresponde a TimeTicks (centésimas de segundo).                               | Reescribirlo: qué hace, cómo correrlo con `uv`, cómo se despliega y un enlace a [docs/arqui/arquitectura_y_uso.md](arqui/arquitectura_y_uso.md).         |
| B9  | Los nombres de las mediciones no son consistentes: humedad y estado comparten `ups_temp2` y el DC usa `dc-ups`.                                                                                                                                                                           | **No cambiarlos todavía**, porque romperían los dashboards de Grafana. Documentarlos y, si se cambian, hacerlo de forma coordinada.                      |
| B10 | `.gitignore` no contempla `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `coverage.xml` ni `htmlcov/`.                                                                                                                                                                                         | Agregarlos.                                                                                                                                              |

---

## 3. Migración a uv y pyproject.toml

### 3.1 Estructura objetivo

```text
monitoreo-ups/
├── pyproject.toml
├── uv.lock                         # versionado
├── .python-version                 # 3.12
├── Dockerfile
├── .dockerignore
├── .gitlab-ci.yml
├── deploy/
│   ├── actualizar.sh               # script del cron (§6)
│   ├── monitoreo.env.example       # plantilla de /etc/monitoreo-ups/monitoreo.env
│   └── telegraf-monitoreo-ups.conf # snippet de Telegraf (§5.4)
├── src/
│   └── monitoreo_ups/
│       ├── __init__.py
│       ├── __main__.py             # permite `python -m monitoreo_ups`
│       ├── main.py                 # def run() -> int
│       ├── config/
│       ├── core/
│       ├── drivers/
│       └── infraestructura/
│           └── schema.sql          # antes data/creacion_tabla_state.sql
└── tests/
```

### 3.2 Pasos

1. Instalar uv en las máquinas de desarrollo (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
2. Mover el código a `src/monitoreo_ups/` y reemplazar los imports `config.` / `core.` / ... por `monitoreo_ups.config.` / ...
3. Mover el SQL dentro del paquete y leerlo con `importlib.resources.files("monitoreo_ups.infraestructura") / "schema.sql"`. Con `--no-editable`, en el contenedor sólo queda el paquete instalado, no el árbol del repo.
4. Crear el `pyproject.toml` (§3.3) y fijar la versión de Python con `uv python pin 3.12`.
5. `uv lock` y versionar `uv.lock`.
6. `uv sync` para crear `.venv/` con todas las dependencias, incluidas las de desarrollo.
7. Borrar `pytest.ini` (su configuración pasa al `pyproject.toml`) y adaptar el Makefile.
8. Comandos del día a día:

   ```bash
   uv run monitoreo-ups          # ejecutar
   uv run pytest                 # tests + cobertura
   uv run ruff check --fix .     # lint
   uv run ruff format .          # formato
   uv run mypy                   # tipado
   uv add <paquete>              # nueva dependencia (actualiza pyproject y lock)
   uv lock --upgrade             # actualizar dependencias
   ```

> Para compilar `easysnmp` localmente sigue haciendo falta `sudo apt install build-essential libsnmp-dev`.

### 3.3 `pyproject.toml` propuesto

```toml
[project]
name = "monitoreo-ups"
version = "2.0.0"
description = "Monitoreo SNMP de UPS del datacenter PSI con salida en line protocol para Telegraf/InfluxDB y alertas a Google Chat."
readme = "README.md"
requires-python = ">=3.12,<3.14"
authors = [
    { name = "Nicolas Piñera" },
    { name = "Juan Vizgarra" },
]
license = { text = "Propietario" }
classifiers = [
    "Private :: Do Not Upload",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "easysnmp>=0.2.6",
    "httplib2>=0.22",        # se puede eliminar si se migra a requests (A5)
    "python-dotenv>=1.0",    # sólo para desarrollo local; en Docker se usa --env-file
    # seqlog se elimina: Seq no se usa (M1)
]

[project.scripts]
monitoreo-ups = "monitoreo_ups.main:run"

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-cov>=5.0",
    "ruff>=0.7",
    "mypy>=1.13",
    "pip-audit>=2.7",
    "types-httplib2",
]

[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/monitoreo_ups"]

[tool.uv]
default-groups = ["dev"]

# ------------------------------------------------------------------ pytest
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "--cov=monitoreo_ups",
    "--cov-report=term-missing",
    "--cov-report=xml",
    "--junitxml=report.xml",
]

# ------------------------------------------------------------------ coverage
[tool.coverage.run]
branch = true
source = ["monitoreo_ups"]

[tool.coverage.report]
fail_under = 80          # empezar en el valor real actual y subirlo en cada fase
show_missing = true
exclude_also = [
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "@abstractmethod",
]

# ------------------------------------------------------------------ ruff
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E", "W",   # pycodestyle
    "F",        # pyflakes
    "I",        # isort
    "B",        # bugbear
    "UP",       # pyupgrade
    "SIM",      # simplify
    "N",        # pep8-naming
    "S",        # bandit (seguridad)
    "PL",       # pylint
    "PT",       # pytest-style
    "RUF",
    "LOG",      # buenas prácticas de logging
    "G",        # formato de mensajes de logging (evita f-strings, ver M1)
]
ignore = [
    "PLR2004",  # magic values: los umbrales viven en config
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004"]

[tool.ruff.format]
quote-style = "double"

# ------------------------------------------------------------------ mypy
[tool.mypy]
python_version = "3.12"
files = ["src", "tests"]
strict = true
warn_unreachable = true
pretty = true

[[tool.mypy.overrides]]
module = ["easysnmp.*"]
ignore_missing_imports = true
```

Notas:

- Si `fail_under = 80` es demasiado alto para el primer merge, arrancar con el valor actual (≈30–40 %, a medir) y subirlo en cada fase. La regla es que **nunca baje**.
- `strict = true` en mypy es viable porque el código es chico. Si bloquea demasiado al principio, usar `strict = false` + `disallow_untyped_defs = true` y endurecerlo después.
- `S` (bandit) cubre los chequeos de seguridad estáticos del código; `pip-audit` cubre las dependencias.

---

## 4. CI/CD: calidad y seguridad

### 4.1 Objetivos

| Etapa                            | Herramienta                                | Bloquea el merge            |
| -------------------------------- | ------------------------------------------ | --------------------------- |
| Lint y formato                   | `ruff check` + `ruff format --check`       | Sí                          |
| Tipado                           | `mypy`                                     | Sí                          |
| Tests y cobertura                | `pytest` + `pytest-cov` (`fail_under`)     | Sí                          |
| Vulnerabilidades en dependencias | `pip-audit` sobre el lock exportado        | Sí                          |
| Build de la imagen               | `docker build` (sin push, no hay registry) | Sí, si el runner lo permite |

Configuración en GitLab:

- **Settings → Merge requests → Pipelines must succeed** activado.
- `main` como **rama protegida**: sólo se mergea por MR con aprobación de CODEOWNERS. Esto importa porque el cron de la VM construye y ejecuta lo que esté en `main` (§6.4).
- Pipeline programado (**CI/CD → Schedules**) semanal sobre `main` que corra `audit`, para enterarse de CVEs nuevas aunque no haya cambios.

### 4.2 `.gitlab-ci.yml` propuesto

```yaml
stages:
  - calidad
  - test
  - seguridad
  - build

variables:
  UV_VERSION: "0.9" # fijar a una versión exacta
  PYTHON_IMAGE: "python:3.12-slim-bookworm"
  UV_CACHE_DIR: "$CI_PROJECT_DIR/.uv-cache"
  UV_LINK_MODE: "copy"
  UV_FROZEN: "1" # usar exactamente uv.lock

workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_PIPELINE_SOURCE == "schedule"

.uv:
  image: $PYTHON_IMAGE
  cache:
    key:
      files: [uv.lock]
    paths: [.uv-cache]
  before_script:
    - apt-get update -qq && apt-get install -y -qq --no-install-recommends build-essential libsnmp-dev
    - pip install --quiet "uv==${UV_VERSION}.*"
    - uv sync --locked
  after_script:
    - uv cache prune --ci

ruff:
  extends: .uv
  stage: calidad
  rules:
    - if: $CI_PIPELINE_SOURCE != "schedule"
  script:
    - uv run ruff check --output-format=gitlab --output-file=gl-code-quality.json . || (uv run ruff check . && false)
    - uv run ruff format --check .
  artifacts:
    when: always
    reports:
      codequality: gl-code-quality.json

mypy:
  extends: .uv
  stage: calidad
  rules:
    - if: $CI_PIPELINE_SOURCE != "schedule"
  script:
    - uv run mypy

pytest:
  extends: .uv
  stage: test
  rules:
    - if: $CI_PIPELINE_SOURCE != "schedule"
  script:
    - uv run pytest
  coverage: '/TOTAL.*? (100(?:\.0+)?\%|[1-9]?\d(?:\.\d+)?\%)$/'
  artifacts:
    when: always
    reports:
      junit: report.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

pip-audit:
  image: $PYTHON_IMAGE
  stage: seguridad
  before_script:
    - pip install --quiet "uv==${UV_VERSION}.*"
  script:
    # Se audita el lock exportado (versiones exactas + hashes), sin compilar easysnmp.
    - uv export --frozen --no-dev --no-emit-project --format requirements-txt -o requirements.txt
    - uvx pip-audit --strict --disable-pip --require-hashes -r requirements.txt
  artifacts:
    when: on_failure
    paths: [requirements.txt]

docker-build:
  stage: build
  image: docker:27
  services: [docker:27-dind]
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - docker build -t monitoreo-ups:ci .
    - docker run --rm --network none --entrypoint python monitoreo-ups:ci -c "import monitoreo_ups"
```

Notas:

- `docker-build` necesita un runner con Docker-in-Docker (modo privilegiado). Si el runner no lo permite, usar `kaniko` o `buildah` con `--no-push`, o quitar el job: el cron de la VM igual valida el build antes de cambiar la imagen productiva (§6).
- `pip-audit --disable-pip` sólo funciona con requisitos con hashes o con `--no-deps`. `uv export` genera hashes por defecto, así que sirve sin instalar nada.
- Si una CVE no tiene fix y el riesgo es aceptable, ignorarla de forma explícita con `--ignore-vuln <ID>` y dejar un comentario con la justificación y una fecha de revisión.
- Mantener las dependencias al día con Renovate (si está disponible en la instancia) o con un `uv lock --upgrade` mensual por MR.

---

## 5. Contenerización

### 5.1 Decisiones

- **Imagen base:** `python:3.12-slim-bookworm`. Build en dos etapas: el builder tiene compilador y `libsnmp-dev`; la imagen final sólo lleva la biblioteca de runtime `libsnmp40`.
- **Usuario no root** (UID fijo `10001`) dentro del contenedor.
- **Contenedor efímero:** Telegraf hace `docker run --rm` en cada intervalo. La imagen no tiene `CMD` de larga duración.
- **Estado fuera de la imagen:** volumen `/var/lib/monitoreo-ups` → `/data` (SQLite). Ver [A6](#a6-el-estado-y-los-secretos-viven-dentro-del-repo).
- **Secretos fuera de la imagen:** `--env-file /etc/monitoreo-ups/monitoreo.env`. **Nunca** hacer `COPY .env`.
- **Red:** `--network host`, para llegar a los UPS por SNMP con la misma resolución DNS y rutas que la VM, sin configurar redes de Docker.
- **stdout limpio:** en stdout sólo puede salir line protocol, los logs van a stderr (M1). No usar `-t` en `docker run`, porque la TTY agrega `\r` y rompe el parseo.

### 5.2 `Dockerfile` propuesto

```dockerfile
# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

# ---------- builder ----------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libsnmp-dev \
 && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 1) Dependencias (capa cacheada mientras no cambie uv.lock)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

# 2) Proyecto
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---------- runtime ----------
FROM python:${PYTHON_VERSION}-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends libsnmp40 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin ups \
 && mkdir -p /data && chown ups /data

COPY --from=builder /app/.venv /app/.venv

ARG GIT_SHA=desconocido
LABEL org.opencontainers.image.title="monitoreo-ups" \
      org.opencontainers.image.revision="${GIT_SHA}"

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MONITOREO_DATA_DIR=/data \
    MONITOREO_VERSION="${GIT_SHA}"

USER ups
VOLUME ["/data"]
ENTRYPOINT ["monitoreo-ups"]
```

> Si el `COPY --from=ghcr.io/...` no funciona porque la VM no tiene salida a ghcr.io, reemplazarlo por `RUN pip install "uv==<versión>"` en el builder.

### 5.3 `.dockerignore`

```text
.git
.gitlab-ci.yml
.venv
venv
.env
*.env
data/*.db
logs
docs
tests
deploy
**/__pycache__
.mypy_cache
.ruff_cache
.pytest_cache
.coverage
coverage.xml
report.xml
```

### 5.4 Ejecución desde Telegraf

Preparación de la VM (una sola vez):

```bash
sudo mkdir -p /var/lib/monitoreo-ups /etc/monitoreo-ups
sudo chown 10001 /var/lib/monitoreo-ups                   # UID del usuario del contenedor
sudo cp <clon_viejo>/data/errores.db /var/lib/monitoreo-ups/   # conservar el estado de alertas
sudo chown 10001 /var/lib/monitoreo-ups/errores.db
sudo install -m 600 -o root -g telegraf deploy/monitoreo.env.example /etc/monitoreo-ups/monitoreo.env
# editar /etc/monitoreo-ups/monitoreo.env con los valores reales
sudo usermod -aG docker telegraf && sudo systemctl restart telegraf
```

> **Seguridad:** pertenecer al grupo `docker` equivale a tener acceso root en la VM. Es aceptable en una VM dedicada al monitoreo; si no lo es, usar Docker rootless o un wrapper con una regla de `sudoers` acotada.

`/etc/monitoreo-ups/monitoreo.env` (plantilla en `deploy/monitoreo.env.example`):

```dotenv
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/...
SNMP_COMMUNITY=...
SNMP_TIMEOUT=1
SNMP_RETRIES=1
LOG_LEVEL=WARNING
MAX_WORKERS=13
```

Snippet de Telegraf (`deploy/telegraf-monitoreo-ups.conf` → `/etc/telegraf/telegraf.d/`):

```toml
[[inputs.exec]]
  commands = [
    "docker run --rm --pull never --network host -v /var/lib/monitoreo-ups:/data --env-file /etc/monitoreo-ups/monitoreo.env monitoreo-ups:prod",
  ]
  interval = "60s"     # mantener el intervalo actual
  timeout  = "50s"     # < interval; medir la duración real tras A5 y ajustar
  data_format = "influx"
```

- `--pull never`: la imagen sólo existe localmente, así que no se intenta buscarla en Docker Hub.
- `monitoreo-ups:prod` es un **alias estable** que el script de deploy mueve recién cuando un build nuevo pasó el smoke test.
- El arranque del contenedor suma alrededor de 0,5–1 s por ejecución, despreciable frente a los tiempos de SNMP.

**Rollback manual:** `docker tag monitoreo-ups:<sha_anterior> monitoreo-ups:prod`. Telegraf toma la imagen anterior en la siguiente ejecución.

---

## 6. Despliegue automático con cron en la VM

### 6.1 Flujo

```text
cron (cada 5 min)
  └─ deploy/actualizar.sh
       ├─ flock: si ya hay un deploy corriendo, sale
       ├─ git fetch origin main
       ├─ ¿HEAD == origin/main y la imagen <sha> existe? → sale (no hay cambios)
       ├─ git reset --hard origin/main + git clean -fd   (la VM nunca tiene cambios locales → sin conflictos)
       ├─ docker build -t monitoreo-ups:<sha>
       ├─ smoke test: docker run --network none ... import monitoreo_ups
       ├─ docker tag monitoreo-ups:<sha> monitoreo-ups:prod   ← recién acá cambia producción
       ├─ borrar tags viejos (conserva los últimos N) + docker image prune -f
       └─ (opcional) avisar a Google Chat del deploy o del fallo
```

Si el build o el smoke test fallan, `:prod` sigue apuntando a la imagen anterior y **el monitoreo no se interrumpe**.

> Aclaración: el comando es `docker image prune`; `docker image purge` no existe. `prune -f` borra sólo las imágenes _dangling_ (sin tag), que son las que deja cada rebuild. Los tags viejos se borran a propósito en el script, y el caché de build se limpia aparte con `docker builder prune`.

### 6.2 `deploy/actualizar.sh` propuesto

```bash
#!/usr/bin/env bash
# Actualiza el clon de main, construye la imagen y la promueve a :prod si pasa el smoke test.
# Pensado para ejecutarse desde cron. Idempotente: si no hay cambios, no hace nada.
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/opt/monitoreo-ups}"
BRANCH="${BRANCH:-main}"
IMAGE="${IMAGE:-monitoreo-ups}"
PROD_TAG="${PROD_TAG:-prod}"
KEEP_IMAGES="${KEEP_IMAGES:-3}"
LOCK_FILE="${LOCK_FILE:-/var/lock/monitoreo-ups-deploy.lock}"
ENV_FILE="${ENV_FILE:-/etc/monitoreo-ups/monitoreo.env}"

log() { echo "$(date --iso-8601=seconds) [deploy] $*"; }

notificar() {
  # Aviso opcional a Google Chat usando el mismo webhook del monitoreo.
  local url
  url="$(grep -E '^GOOGLE_CHAT_WEBHOOK_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
  [[ -n "$url" ]] || return 0
  curl -fsS --max-time 10 -H 'Content-Type: application/json' \
       -d "{\"text\": \"$1\"}" "$url" >/dev/null || true
}

main() {
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "Otro deploy en curso, salgo."
    exit 0
  fi

  cd "$REPO_DIR"
  git fetch --quiet origin "$BRANCH"

  local local_sha remote_sha short_sha
  local_sha="$(git rev-parse HEAD)"
  remote_sha="$(git rev-parse "origin/$BRANCH")"
  short_sha="$(git rev-parse --short=12 "origin/$BRANCH")"

  if [[ "$local_sha" == "$remote_sha" ]] && docker image inspect "$IMAGE:$short_sha" >/dev/null 2>&1; then
    exit 0  # nada que hacer
  fi

  log "Actualizando $local_sha -> $remote_sha"
  git reset --hard --quiet "origin/$BRANCH"
  git clean -fd --quiet

  log "Construyendo $IMAGE:$short_sha"
  docker build --pull \
    --build-arg GIT_SHA="$short_sha" \
    -t "$IMAGE:$short_sha" .

  log "Smoke test"
  docker run --rm --network none --entrypoint python "$IMAGE:$short_sha" \
    -c "import monitoreo_ups.main"

  docker tag "$IMAGE:$short_sha" "$IMAGE:$PROD_TAG"
  log "Promovida $IMAGE:$short_sha a :$PROD_TAG"

  # Conservar las últimas KEEP_IMAGES versiones (además de :prod) para rollback
  docker image ls "$IMAGE" --format '{{.Tag}}' \
    | grep -vE "^($PROD_TAG|<none>)$" \
    | tail -n +"$((KEEP_IMAGES + 1))" \
    | xargs -r -I{} docker image rm "$IMAGE:{}" >/dev/null || true
  docker image prune -f >/dev/null
  docker builder prune -f --filter "until=168h" >/dev/null || true

  notificar "✅ monitoreo-ups desplegado: ${short_sha}"
}

trap 'log "ERROR en línea $LINENO"; notificar "❌ Falló el deploy de monitoreo-ups (ver /var/log/monitoreo-ups/deploy.log)"' ERR

# Todo el cuerpo está en main(): bash lee el script completo antes de ejecutarlo,
# así un `git reset` que modifique este archivo no afecta a la ejecución en curso.
main "$@"
```

`docker image ls` lista de más nuevo a más viejo, así que `tail -n +N` deja afuera las N más recientes.

### 6.3 Instalación en la VM

```bash
# 1. Usuario de servicio con acceso a docker (no usar el usuario personal)
sudo useradd --system --create-home --groups docker deploy-ups

# 2. Deploy token de sólo lectura (GitLab → Settings → Repository → Deploy tokens, scope read_repository)
sudo -u deploy-ups git clone https://<token_user>:<token>@<gitlab>/<grupo>/monitoreo-ups.git /opt/monitoreo-ups
#    (o una deploy key SSH de sólo lectura)

# 3. Log
sudo mkdir -p /var/log/monitoreo-ups && sudo chown deploy-ups /var/log/monitoreo-ups

# 4. Primer deploy manual
sudo -u deploy-ups /opt/monitoreo-ups/deploy/actualizar.sh

# 5. Cron (crontab -e -u deploy-ups)
*/5 * * * * /opt/monitoreo-ups/deploy/actualizar.sh >> /var/log/monitoreo-ups/deploy.log 2>&1

# 6. Rotación del log (/etc/logrotate.d/monitoreo-ups)
/var/log/monitoreo-ups/deploy.log { weekly rotate 8 compress missingok notifempty }
```

Cambiar `LOCK_FILE` a una ruta donde `deploy-ups` pueda escribir si `/var/lock` no lo permite.

> Un `systemd timer` reemplaza bien a cron: da logs en `journalctl` y evita ejecuciones superpuestas de forma nativa. Es opcional; cron + `flock` alcanza.

### 6.4 Consideraciones

- **Seguridad de la cadena de deploy:** lo que llega a `main` se construye y ejecuta en la VM con permisos de docker. Por eso `main` tiene que estar protegida, con MR obligatorio y el pipeline en verde (§4.1). El clon usa un token de **sólo lectura**.
- **Sin conflictos:** la VM no tiene cambios propios (el estado y los secretos están fuera del clon), así que `git reset --hard` es seguro y reemplaza al `git pull` manual.
- **Latencia del deploy:** como mucho 5 minutos más la duración del build. El build es rápido mientras no cambie `uv.lock`, gracias al caché de capas.
- **Salida a internet:** el build necesita llegar a Docker Hub (imagen base), ghcr.io (uv) y PyPI. Si la VM sale por un proxy, configurarlo en `/etc/systemd/system/docker.service.d/` y pasarlo como `--build-arg`.
- **Cambiar la VM sin tocar el repo:** si cambian el webhook, los timeouts o el nivel de log, se edita `/etc/monitoreo-ups/monitoreo.env` y no hace falta un deploy.

---

## 7. Hoja de ruta por fases

Cada fase es un MR independiente, en este orden. Las fases 1 y 2 se pueden hacer en paralelo con la fase 0.

### Fase 0 — Bugs críticos (sobre el código actual)

- [ ] A2: aislar cada driver en `try/except` y salir con código 0 si hubo métricas.
- [ ] A4 / A3: `ClienteSNMP` devuelve `float | None` y detecta `NOSUCH*`.
- [ ] A1: no publicar ni validar métricas sin dato; agregar el error `SIN_RESPUESTA_SNMP`.
- [ ] A5: timeouts de SNMP y HTTP; quitar `time.sleep(1)`.
- [ ] A8: persistir el cambio de estado sólo si la notificación salió bien.
- [ ] M2: imprimir desde el hilo principal.
- [ ] Tests para cada uno de los puntos anteriores, con un cliente SNMP falso.

### Fase 1 — uv + pyproject + reestructura del paquete

- [ ] Mover el código a `src/monitoreo_ups/`, el SQL a `schema.sql` dentro del paquete y renombrar `test/` a `tests/` (B1, B3).
- [ ] `pyproject.toml` (§3.3), `uv.lock` y `.python-version`.
- [ ] Entry point `monitoreo-ups` y `__main__.py`; `main.run()` devuelve un código de salida.
- [ ] `ruff check --fix` + `ruff format` en un **commit aparte** (para no ensuciar el diff funcional).
- [ ] Eliminar `scrip/`, `pytest.ini` y los shebangs; actualizar el Makefile y `.gitignore` (B2, B6, B7, B10).

### Fase 2 — CI

- [ ] Nuevo `.gitlab-ci.yml` (§4.2).
- [ ] Type hints hasta que `mypy` pase (B5).
- [ ] Fijar `fail_under` en la cobertura real y subirlo.
- [ ] Proteger `main` y activar "Pipelines must succeed".
- [ ] Pipeline programado semanal para `pip-audit`.

### Fase 3 — Configuración externa + Docker

- [ ] Rutas, comunidad SNMP, webhook, timeouts y nivel de log por variables de entorno (A6, M7).
- [ ] M1: `uv remove seqlog`, `logging` estándar a stderr configurado dentro de `run()`, reescribir las llamadas con kwargs y borrar el código y la documentación de logging muertos.
- [ ] `Dockerfile`, `.dockerignore` y `deploy/monitoreo.env.example`.
- [ ] Validar que `easysnmp` compila en la imagen (M9); si no, migrar a `ezsnmp`.
- [ ] Probar la imagen en la VM **en paralelo** al esquema actual: escribir a un bucket o measurement de prueba, con otra base SQLite y **sin webhook**, para no duplicar alertas.

### Fase 4 — Deploy automático y corte

- [ ] `deploy/actualizar.sh` y su instalación (§6.3).
- [ ] Copiar `errores.db` al volumen, crear `/etc/monitoreo-ups/monitoreo.env` y agregar `telegraf` al grupo `docker`.
- [ ] Cambiar el `[[inputs.exec]]` de Telegraf al `docker run` y verificar en Grafana que no haya huecos.
- [ ] Hacer un cambio trivial en `main` y comprobar que se despliega solo en menos de 10 minutos.
- [ ] Probar un rollback manual.
- [ ] Retirar el clon viejo y las dependencias instaladas con `apt`.

### Fase 5 — Mejoras de dominio

- [ ] M4: contrato `BaseUPS` homogéneo, con OIDs inyectados y `ejecutar()` sin argumentos.
- [ ] M6: reglas de validación declarativas, mensajes formateados en el notificador y uso del `Enum` en lugar de strings.
- [ ] M3: alertas para el UPS trifásico del DC.
- [ ] M5: elegir el modelo de la tabla (estado o historial), `UNIQUE`, WAL y cierre de conexiones.
- [ ] M8: control de los futures.
- [ ] B8: reescribir el README y actualizar `docs/arqui/` y `docs/logger/`.

---

## 8. Preguntas abiertas

1. ¿Cuál es el `interval` y el `timeout` actual del `[[inputs.exec]]` en Telegraf? Hacen falta para dimensionar los timeouts de SNMP (A5).
2. ¿El runner de GitLab permite Docker-in-Docker (modo privilegiado)? Define si `docker-build` corre en el CI (§4.2).
3. ¿La VM tiene salida directa a Docker Hub, ghcr.io y PyPI, o sale por un proxy? (§6.4)
4. ¿La tabla `errores` se quiere como estado actual o como historial de incidentes? (M5)
5. ¿Qué umbrales corresponden al UPS trifásico del DC? (M3)
6. ¿Algún UPS tiene firmware viejo que use `OIDTNEW`? Sirve para probar A4 contra un equipo real.
