.PHONY: install run test lint format typecheck audit check docker-build docker-run

install:
	uv sync

run:
	uv run python src/main.py

test:
	uv run pytest --cov

lint:
	uv run ruff check .
	uv run ruff format --check .
	uvx --from shellcheck-py==0.10.0.1 shellcheck deploy/*.sh

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

audit:
	uv export --frozen --no-dev --no-emit-project --format requirements-txt -o /tmp/req.txt
	uvx pip-audit --strict --disable-pip --require-hashes -r /tmp/req.txt

check: lint typecheck test audit   # lo mismo que el CI

# ---------------------------------------------------------------- Docker
GIT_SHA := $(shell git rev-parse --short=12 HEAD)

docker-build:   # imagen etiquetada con el commit y como :prod (la que usa compose.yaml)
	docker build --build-arg GIT_SHA=$(GIT_SHA) -t monitoreo-ups:$(GIT_SHA) -t monitoreo-ups:prod .

docker-run:     # una ejecucion, igual que Telegraf (necesita MONITOREO_UID/GID en el .env)
	docker compose run --rm -T monitoreo
