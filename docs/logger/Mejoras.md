# Logging del monitoreo UPS

> Estado actual, después de M1 del [plan de mejora v2](../plan_de_mejora_v2.md). Reemplaza la versión anterior de este documento, que describía una implementación que nunca llegó al código.

## Regla principal

**stdout es sólo para Telegraf.** Lo único que se escribe en stdout son las líneas de line protocol (`ups_temp2,host=... battery=...`). Cualquier otro texto ahí hace que Telegraf no pueda parsear la salida. Por eso el logging nunca escribe en stdout, y un test lo verifica (`test_nunca_escribe_en_stdout`).

## A dónde van los logs

**Sólo al archivo `data/logs/monitoreo.log`** (rotativo), desde `INFO` (configurable). No se escribe nada por consola: ni en stdout (reservado para Telegraf) ni en stderr. Para seguir una ejecución: `tail -f data/logs/monitoreo.log`.

- **Rotación:** `monitoreo.log` rota a los 5 MB y se guardan 5 archivos viejos (`monitoreo.log.1` … `monitoreo.log.5`). Como máximo ocupa unos 30 MB.
- **Formato:**

  ```text
  2026-10-09 14:32:05,123 WARNING infraestructura.snmp_client [ThreadPoolExecutor-0_3] Timeout SNMP en f1r2u1.psi.unc.edu.ar (oid=1.3.6.1.4.1.318.1.1.1.2.2.2.0)
  ```

  Cada línea tiene: fecha · nivel · módulo que escribió el log · hilo (útil porque los UPS se consultan en paralelo) · mensaje.

- **Si no se puede crear el archivo** (falta de permisos, disco lleno), el monitoreo sigue funcionando y los logs van a stderr desde `WARNING`, con un aviso de por qué. Es el único caso en que aparece algo por consola; así los errores no se pierden.

## Configuración

En el `.env` de la raíz del repo o como variables de entorno del proceso (ver [.env.example](../../.env.example) y `src/config/entorno.py`). La configuración se carga **antes** de configurar el logging, así que las dos se leen del `.env`.

| Variable | Por defecto | Ejemplo |
| --- | --- | --- |
| `MONITOREO_DATA_DIR` | `data` (relativa a la raíz del repo) | `/app/data` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `WARNING` |

- Los logs van a `<MONITOREO_DATA_DIR>/logs/`, junto a la base: con Docker, un solo volumen cubre las dos cosas.
- `LOG_LEVEL` controla qué llega al archivo. Un valor inválido hace que el monitoreo no arranque y explique el error en stderr.
- Para depurar sin editar el `.env`: `LOG_LEVEL=DEBUG python src/main.py` (el entorno del proceso gana sobre el archivo).

## Cómo escribir logs en el código

```python
import logging

logger = logging.getLogger(__name__)

logger.warning("Timeout SNMP en %s (oid=%s)", host, oid)  # bien: formato %s del módulo logging
logger.exception(
    "Error al ejecutar StateUPS para %s", host
)  # dentro de un except: agrega el traceback

logger.warning(f"Timeout SNMP en {host}")  # evitar: f-string
logger.warning("Timeout SNMP", host=host)  # NO: lanza TypeError (era sintaxis de seqlog)
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
