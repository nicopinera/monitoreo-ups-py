# syntax=docker/dockerfile:1
# Imagen del monitoreo de UPS. Se ejecuta una vez por intervalo de Telegraf con
# `docker compose run --rm -T monitoreo` (ver compose.yaml) y termina.
#
# Construir: docker build --build-arg GIT_SHA=$(git rev-parse --short=12 HEAD) -t monitoreo-ups:prod .

ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- etapa 1: dependencias
# Tiene uv y arma el .venv. Nada de esta etapa queda en la imagen final salvo el .venv.
FROM python:${PYTHON_VERSION}-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Solo pyproject.toml y uv.lock: esta capa se reutiliza mientras no cambien las dependencias.
# El proyecto no se instala (package = false): solo sus dependencias, sin las de desarrollo.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev

# ---------------------------------------------------------------- etapa 2: imagen final
FROM python:${PYTHON_VERSION}-slim-trixie

# Usuario sin privilegios. En produccion compose lo reemplaza por el UID del duenio del clon
# (user: en compose.yaml), para que los archivos del volumen tengan el mismo duenio afuera.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin ups

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src

ARG GIT_SHA=desconocido
LABEL org.opencontainers.image.title="monitoreo-ups" \
      org.opencontainers.image.revision="${GIT_SHA}"

# PYTHONPATH permite `python -c "import main"` (smoke test del CI y del deploy).
# La base y los logs van a /app/data (RUTA_RAIZ es /app): ahi se monta el volumen.
# No se declara VOLUME: si se corre sin montar /app/data falla a la vista en lugar de crear
# volumenes anonimos que se acumulan.
# TZ: sin ella el contenedor usa UTC y la hora de los mensajes y del log sale 3 h adelantada.
# La imagen base trae tzdata. Se puede cambiar con TZ en el .env (compose la pasa con env_file).
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app/src \
    TZ=America/Argentina/Cordoba \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER ups
ENTRYPOINT ["python", "/app/src/main.py"]
