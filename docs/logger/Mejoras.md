# Logging del monitoreo UPS

> Estado actual, después de M1 del [plan de mejora v2](../plan_de_mejora_v2.md). Reemplaza la versión anterior de este documento, que describía una implementación que nunca llegó al código.

## Regla principal

**stdout es sólo para Telegraf.** Lo único que se escribe en stdout son las líneas de line protocol (`ups_temp2,host=... battery=...`). Cualquier otro texto ahí hace que Telegraf no pueda parsear la salida. Por eso el logging nunca escribe en stdout, y un test lo verifica (`test_nunca_escribe_en_stdout`).

## A dónde van los logs

| Destino | Qué llega | Para qué sirve |
| --- | --- | --- |
| `logs/monitoreo.log` (archivo rotativo) | Todo desde `INFO` (configurable) | Historial para revisar qué pasó en ejecuciones anteriores |
| stderr | Sólo `WARNING`, `ERROR` y `CRITICAL` | Ver problemas al correrlo a mano. Telegraf lo muestra en su log cuando la ejecución termina con error |

- **Rotación:** `monitoreo.log` rota a los 5 MB y se guardan 5 archivos viejos (`monitoreo.log.1` … `monitoreo.log.5`). Como máximo ocupa unos 30 MB.
- **Formato:**

  ```text
  2026-10-09 14:32:05,123 WARNING infraestructura.snmp_client [ThreadPoolExecutor-0_3] Timeout SNMP en f1r2u1.psi.unc.edu.ar (oid=1.3.6.1.4.1.318.1.1.1.2.2.2.0)
  ```

  Cada línea tiene: fecha · nivel · módulo que escribió el log · hilo (útil porque los UPS se consultan en paralelo) · mensaje.

- **Si no se puede crear el archivo** (falta de permisos, disco lleno), el monitoreo sigue funcionando sólo con stderr y lo avisa con un warning.

## Configuración

Por variables de entorno del proceso. En Telegraf se definen con la opción `environment` de `[[inputs.exec]]`; con Docker, con `--env-file`.

| Variable | Por defecto | Ejemplo |
| --- | --- | --- |
| `MONITOREO_LOG_DIR` | `logs/` en la raíz del repo | `/data/logs` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `WARNING` |

`LOG_LEVEL` controla qué llega al archivo; stderr siempre muestra desde `WARNING`. Un valor inválido se toma como `INFO`.

> Estas variables **no** se leen del `.env` del repo, porque el `.env` se carga recién al crear el notificador, después de configurar el logging. Esto se unifica en el paso 12 del plan (configuración por variables de entorno).

## Cómo escribir logs en el código

```python
import logging

logger = logging.getLogger(__name__)

logger.warning("Timeout SNMP en %s (oid=%s)", host, oid)    # bien: formato %s del módulo logging
logger.exception("Error al ejecutar StateUPS para %s", host) # dentro de un except: agrega el traceback

logger.warning(f"Timeout SNMP en {host}")                    # evitar: f-string
logger.warning("Timeout SNMP", host=host)                    # NO: lanza TypeError (era sintaxis de seqlog)
```

Niveles:

- `INFO`: eventos normales, por ejemplo "Iniciando monitoreo UPS".
- `WARNING`: problemas esperables y recuperables, como el timeout de un UPS.
- `ERROR`: fallos que impiden una parte del trabajo, como que no se pueda enviar a Google Chat.
- `exception`: lo mismo que `ERROR`, pero con el traceback; usarlo dentro de un `except`.

## Dónde se configura

- [src/infraestructura/logger.py](../../src/infraestructura/logger.py): la función `configurar_logger()`.
- [src/config/configuracion.py](../../src/config/configuracion.py): la carpeta, el nombre del archivo, el tamaño y la cantidad de backups.
- [src/main.py](../../src/main.py): llama a `configurar_logger()` sólo al ejecutarse como programa, no al importarse.

## Historia

Antes se usaba `seqlog` para enviar los logs a un servidor Seq en `localhost:5341`. Seq no se usa, así que se eliminó. Además, las llamadas con argumentos propios de seqlog (`host=...`) lanzaban `TypeError` con el logging estándar, y eso hacía que un error ya manejado (por ejemplo, un timeout SNMP) terminara en una excepción nueva.
