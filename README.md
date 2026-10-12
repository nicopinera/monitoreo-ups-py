# Monitoreo UPS

Monitoreo por SNMP de los UPS del Data Center del Pabellón Argentina (Prosecretaría de Informática, UNC). Cada minuto Telegraf ejecuta el módulo, que consulta los equipos en paralelo, imprime sus métricas en line protocol (InfluxDB → Grafana) y avisa en Google Chat cuando una alerta aparece o se resuelve.

- **26 UPS APC**: temperatura de baterías y ambiente, carga de baterías y de salida, autonomía y corriente, con alertas por umbral.
- **UPS trifásico del DC** y **sensor de humedad**: métricas, con alerta solo si dejan de responder.
- **Alertas** como tarjetas de Google Chat, un hilo por incidente (la resolución responde en el hilo de su alerta, con la duración).

## Documentación

| Documento | Para qué |
| --- | --- |
| [docs/monitoreo-ups.md](docs/monitoreo-ups.md) | Guía de uso y operación (la página de BookStack): instalación, alertas, cómo actualizar. |
| [docs/arqui/arquitectura_y_uso.md](docs/arqui/arquitectura_y_uso.md) | Cómo está armado el código y cómo extenderlo. |
| [docs/runbook_vm.md](docs/runbook_vm.md) | Instalación en la VM paso a paso, rollback y problemas comunes. |
| [docs/logging.md](docs/logging.md) | Dónde van los logs y cómo escribirlos. |
| [docs/plan_de_mejora_v2.md](docs/plan_de_mejora_v2.md) | Registro de la revisión de 2026 y de cada cambio que salió de ella. |

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/) (instala Python 3.13 solo si hace falta).

```bash
make install      # entorno virtual con las dependencias (uv sync)
cp .env.example .env   # y completar: SNMP_COMMUNITY y, para probar alertas, un webhook de PRUEBA
make run          # una ejecución, igual que Telegraf (necesita llegar a los UPS: VPN)
make check        # lo mismo que el CI: ruff, mypy, pytest (cobertura ≥ 90 %) y pip-audit
```

| Comando | Qué hace |
| --- | --- |
| `make test` | Tests con cobertura. |
| `make lint` / `make format` | Revisa / corrige el formato (ruff) y los scripts de `deploy/` (shellcheck). |
| `make typecheck` | mypy en modo estricto. |
| `make docker-build` / `make docker-run` | Construye la imagen y la ejecuta con `compose.yaml`, como en la VM. |
| `make probar-tarjetas WEBHOOK='https://…'` | Envía tarjetas de ejemplo a un webhook de **prueba** para ver cómo quedan. |

La configuración (secretos, timeouts, nivel de log) va en el `.env` y está explicada en [.env.example](.env.example). Lo que no depende del entorno (hosts, OIDs, umbrales de alerta) está en [src/config/configuracion.py](src/config/configuracion.py) y se cambia por Merge Request.

## Despliegue

La VM `pdu-monitoreo` ejecuta el módulo en un contenedor Docker (`docker compose run`, ver [compose.yaml](compose.yaml)). Cada 5 minutos un cron ([deploy/actualizar.sh](deploy/actualizar.sh)) busca commits nuevos en `main`, construye la imagen, la prueba y recién entonces la pasa a producción. Un merge a `main` llega solo a la VM; si el build o la prueba fallan, sigue la versión anterior y se avisa en el chat.

Flujo: rama → MR a `dev` (pipeline en verde) → MR `dev` → `main` → deploy automático.

## Estructura

```text
src/
├── main.py              orquestador: arma los drivers, los ejecuta en paralelo, imprime y sale
├── config/              configuracion.py (hosts, OIDs, reglas) y entorno.py (.env)
├── core/                dominio: reglas de alerta, contrato de los drivers, gestor de alertas
├── drivers/             un driver por tipo de equipo (UPS APC, UPS del DC, sensor de humedad)
└── infraestructura/     SNMP, SQLite, Google Chat (tarjetas) y logging
tests/                   pytest, con dobles que reemplazan la red y el chat
deploy/                  deploy automático: script, cron, input de Telegraf y logrotate
scripts/                 probar_tarjetas.py
```
