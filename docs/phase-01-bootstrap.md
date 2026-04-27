# Phase 1: Bootstrap + Git

## Goal

Establish the main PrepSuite backend repository with a production-ready service skeleton, local infrastructure, quality gates, and documentation.

## Data Modeling

No tenant-owned domain tables are introduced in this phase. The shared SQLAlchemy base defines conventions for future tables:

- UUID primary keys.
- Timestamp columns.
- Stable database constraint naming for Alembic.

## Runtime Classes and Functions

- `Settings`: Pydantic v2 settings with local, test, and production support.
- `build_engine`, `build_session_factory`, `get_db_session`: async SQLAlchemy setup.
- `check_database_ready`, `check_redis_ready`: dependency readiness probes.
- `RequestIDMiddleware`: request correlation header handling.
- `StructuredAccessLogMiddleware`: structured JSON access logs.
- `PrepSuiteError`: application error type rendered through the standard error envelope.
- `EventDispatcher`: in-process event shell for later phases.
- `celery_app`: Redis-backed Celery shell.

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Confirms the API process is alive. |
| `GET` | `/api/v1/ready` | Confirms PostgreSQL and Redis are reachable. |

## Local Review

```bash
uv sync --all-groups
make check
docker compose up --build
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
```

## Completion Gate

Phase 1 is complete when linting, type checks, tests, Alembic upgrade, Docker healthchecks, docs, git commit, and git tag all pass locally.
