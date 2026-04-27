.PHONY: install lint format typecheck test check migrate seed up down logs run worker beat

install:
	uv sync --all-groups

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app

test:
	uv run pytest

check: lint typecheck test

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m scripts.seed_app_catalog

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	uv run celery -A app.worker.celery_app worker --loglevel=INFO

beat:
	uv run celery -A app.worker.celery_app beat --loglevel=INFO
