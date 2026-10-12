# Logging del monitoreo UPS

## Regla principal

**stdout es solo para Telegraf.** Lo único que se escribe en stdout son las líneas de line protocol (`ups_temp2,host=... battery=...`). Cualquier otro texto ahí hace que Telegraf no pueda parsear la salida. Por eso el logging nunca escribe en stdout, y un test lo verifica (`test_nunca_escribe_en_stdout`).

## A dónde van los logs

**Solo al archivo `data/logs/monitoreo.log`** (rotativo), desde `INFO` (configurable). No se escribe nada por consola. Para seguir una ejecución:

```bash
tail -f data/logs/monitoreo.log                                          # en desarrollo
sudo -u telegraf tail -f /etc/telegraf/monitoreo-ups/data/logs/monitoreo.log   # en la VM
```

- **Rotación:** rota a los 5 MB y se guardan 5 archivos viejos (`monitoreo.log.1` … `monitoreo.log.5`). Como máximo ocupa unos 30 MB.
- **Formato:**

  ```text
  2026-10-12 17:21:33,917 INFO core.gestor_alertas [ThreadPoolExecutor-0_1] f3r11u1 sin respuesta SNMP (2 de 3 ejecuciones seguidas para avisar)
  ```

  Cada línea tiene: fecha y hora local · nivel · módulo que escribió el log · hilo (los equipos se consultan en paralelo) · mensaje.

- **Hora:** la del contenedor, que usa `TZ=America/Argentina/Cordoba` (definida en el `Dockerfile`, se puede cambiar con `TZ` en el `.env`). Sin `TZ`, un contenedor usa UTC y los logs salen 3 h adelantados.
- **Si no se puede crear el archivo** (permisos, disco lleno), el monitoreo sigue funcionando y los logs van a stderr desde `WARNING`, con un aviso de por qué. Es el único caso en que aparece algo por consola: así los errores no se pierden. Telegraf muestra el stderr en su journal (`journalctl -u telegraf`).

El deploy automático escribe aparte, en `data/logs/deploy.log` (lo rota `logrotate`; ver el [runbook](runbook_vm.md)).

## Qué se registra

| Nivel | Ejemplos |
| --- | --- |
| `DEBUG` | Un OID que el equipo no tiene (por ejemplo, `OIDT` en firmware nuevo, que usa `OIDTNEW`). |
| `INFO` | Inicio de la ejecución; un equipo sin respuesta que todavía no llegó al umbral para avisar. |
| `WARNING` | Un UPS que no responde (timeout SNMP); una alerta que no se pudo avisar y se reintenta en la próxima ejecución; tareas que fallaron. |
| `ERROR` | Respuesta de error de Google Chat (con el status y el cuerpo, por ejemplo 400 si una tarjeta tiene un campo inválido); webhook no configurado; ninguna métrica en toda la ejecución. |
| `exception` | Un error inesperado en un equipo o al procesar sus alertas, con el traceback. |

## Configuración

En el `.env` o como variables del proceso (ver [.env.example](../.env.example) y `src/config/entorno.py`). La configuración se carga **antes** que el logging, así que las dos salen del `.env`.

| Variable | Por defecto | Ejemplo |
| --- | --- | --- |
| `MONITOREO_DATA_DIR` | `data` (relativa a la raíz del repo; en Docker, `/app/data`) | `/tmp/prueba` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `WARNING` |

- Los logs van a `<MONITOREO_DATA_DIR>/logs/`, junto a la base: con Docker, un solo volumen cubre las dos cosas.
- Un `LOG_LEVEL` inválido hace que el monitoreo no arranque y explique el error en stderr.
- Para depurar sin editar el `.env`: `LOG_LEVEL=DEBUG uv run python src/main.py` (el entorno del proceso gana sobre el archivo).

## Cómo escribir logs en el código

```python
import logging

logger = logging.getLogger(__name__)

logger.warning(
    "Sin respuesta SNMP de %s (oid=%s)", host, oid
)  # bien: formato %s del módulo logging
logger.exception("Error al ejecutar %s", nombre)  # dentro de un except: agrega el traceback

logger.warning(
    f"Sin respuesta de {host}"
)  # evitar: f-string (se arma aunque el nivel no se registre)
```

- `INFO`: eventos normales.
- `WARNING`: problemas esperables y recuperables.
- `ERROR`: fallos que impiden una parte del trabajo.
- `exception`: lo mismo que `ERROR`, con el traceback; solo dentro de un `except`.

## Dónde se configura

- [src/infraestructura/logger.py](../src/infraestructura/logger.py): `configurar_logger()`.
- [src/config/configuracion.py](../src/config/configuracion.py): nombre del archivo, tamaño y cantidad de backups.
- [src/main.py](../src/main.py): llama a `configurar_logger()` solo al ejecutarse como programa, no al importarse (los tests importan `main` sin crear archivos).

## Historia

Antes se usaba `seqlog` para enviar los logs a un servidor Seq que no se usaba, y las llamadas con argumentos propios de seqlog (`host=...`) lanzaban `TypeError` con el logging estándar. Se reemplazó por `logging` estándar en el paso M1 del [plan de mejora](plan_de_mejora_v2.md).
