# Mejoras del sistema de logging

## 1. Qué se agregó

Se creó un logger centralizado en `src/config/logger.py` que ahora administra:

- `logs/app.log` para eventos normales y de información (`INFO+`).
- `logs/errors.log` para errores y críticos (`ERROR+`).
- Salida en consola para monitoreo en vivo (`INFO+`).
- Un logger separado `telegraf` para imprimir métricas en formato puro a stdout.

Además, se agregó un archivo `logs/.gitignore` para que los archivos de log no se suban al repositorio.

## 2. Cómo cambia el comportamiento general

### Antes

- El código usaba `print()` en varios módulos para errores y métricas.
- No había un punto único para almacenar eventos o errores.
- Las métricas para Grafana se mezclaban potencialmente con otros mensajes.
- El sistema no diferenciaba bien entre eventos normales e incidentes.

### Ahora

- El logger raíz centralizado recoge todos los mensajes de los módulos que lo usan.
- Los errores y excepciones se guardan en `errors.log` con trazas completas cuando corresponde.
- Los eventos normales siguen en `app.log` y en consola.
- Las métricas de Telegraf (output para Grafana/Influx) se emiten por un logger independiente que no se propaga al logger raíz.

## 3. Qué respetó de `docs/Loggin.md`

### Separación de métricas Telegraf y logs

Sí, el comportamiento principal está respetado:

- El logger `telegraf` escribe sólo la línea de métricas.
- Esta salida no se duplica en `app.log` ni en `errors.log`.
- Mantiene el formato puro `%(message)s` para que Telegraf capture exactamente la métrica.

### Rotación de logs

Se implementó con `RotatingFileHandler`:

- `app.log` y `errors.log` rotan a 10 MB.
- Se conservan hasta 5 archivos antiguos.
- Esto evita que se llene el disco.

### Niveles de severidad

- `INFO` para eventos normales y de orquestación.
- `WARNING` / `ERROR` / `CRITICAL` para problemas reales.
- `DEBUG` se mantiene posible, pero no es el foco principal. Esto coincide con tu observación de que los detalles técnicos no son la prioridad.

## 4. Qué módulos cambiaron y cómo

### `src/main.py`

- Se inicializa el logger.
- Se registra el inicio del monitoreo.
- Se captura y registra un error fatal si el main falla.

### `src/infraestructura/database.py`

- Se reemplazó el `print()` por `logger.error()` al fallar la creación de tablas.

### `src/infraestructura/snmp_client.py`

- Se registra un `WARNING` ante timeouts SNMP.
- Se registra un `ERROR` con `exc_info=True` para otros fallos SNMP.

### `src/infraestructura/notificador.py`

- Se reemplazaron los `print()` por `logger.error()`.
- Se conserva la lógica de notificación, pero con reporte de fallo adecuado.

### `src/drivers/state_ups.py`, `src/drivers/dc_ups.py`, `src/drivers/hum_ups.py`

- Las métricas ahora se envían por `telegraf_logger`.
- En `StateUPS`, las excepciones se registran con `logger.exception()`.

## 5. Qué no se rompió y qué no era la prioridad

- Las funcionalidades de `DEBUG` y `INFO` se mantuvieron como estaban: el sistema puede seguir usándolas si se agregan mensajes futuros.
- La mejora principal fue centralizar y profesionalizar el manejo de errores / warnings / críticos.
- En otras palabras: sí, se respetó la idea de que el valor nuevo está en el reporte de incidentes, no en reescribir todos los `INFO` / `DEBUG`.

## 6. Resultado final esperado

- `logs/app.log`: historial de eventos operativos.
- `logs/errors.log`: historial de fallos y excepciones.
- Consola: información útil para monitoreo en vivo.
- Stdout puro de métricas: captura limpia por Telegraf.

## 7. Archivos agregados

- `logs/.gitignore`
- `Mejoras.md`

---

Si querés, puedo dejar también un checkpoint con ejemplos de líneas que se van a ver en `app.log` y `errors.log`. 