.PHONY: install run test lint format typecheck audit check

install:
	uv sync

run:
	uv run python src/main.py

test:
	uv run pytest --cov

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

audit:
	uv export --frozen --no-dev --no-emit-project --format requirements-txt -o /tmp/req.txt
	uvx pip-audit --strict --disable-pip --require-hashes -r /tmp/req.txt

check: lint typecheck test audit   # lo mismo que el CI
