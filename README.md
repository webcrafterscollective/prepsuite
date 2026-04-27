# PrepSuite Backend

PrepSuite is a production-grade, multi-tenant learning management SaaS backend. This repository starts with Phase 1: the backend bootstrap, service shell, local infrastructure, testing harness, and documentation baseline.

## Stack

- Python 3.12+
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x async ORM
- Alembic
- Pydantic v2
- Redis
- Celery
- Docker Compose
- Pytest, Ruff, Mypy
- uv

## Local Setup

```bash
uv sync --all-groups
cp .env.example .env.local
docker compose up --build
```

The main API is available at:

- Health: `http://localhost:8000/api/v1/health`
- Readiness: `http://localhost:8000/api/v1/ready`
- OpenAPI: `http://localhost:8000/api/v1/openapi.json`
- Swagger UI: `http://localhost:8000/docs`

## Development Commands

```bash
make lint
make typecheck
make test
make migrate
make check
```

## Phase 1 Status

Phase 1 establishes the clean architecture skeleton, async database setup, Alembic, Redis readiness checks, Celery shell, Docker services, structured logging, request IDs, CORS, error handling, and baseline tests.

See `docs/phase-01-bootstrap.md` for the implementation map and review checklist.
