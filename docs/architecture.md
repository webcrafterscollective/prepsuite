# Architecture

PrepSuite uses a modular monolith for the main backend. Each module is a bounded context with thin routers, use-case services, repositories, schemas, permission policies, events, migrations, and tests.

## Phase 1 Components

- `app/main.py`: FastAPI app factory and system routes.
- `app/core/config.py`: environment-based Pydantic settings.
- `app/core/database.py`: async SQLAlchemy engine, session factory, and readiness check.
- `app/core/cache.py`: Redis readiness check.
- `app/core/logging.py`: JSON structured logging and request ID middleware.
- `app/core/exceptions.py`: consistent error response handlers.
- `app/worker.py`: Celery app shell backed by Redis.
- `app/shared/*`: base models, schemas, repositories, and service primitives.

## Clean Architecture Rules

Routers orchestrate HTTP concerns only. Services own business workflows. Repositories own persistence queries. Core dependencies expose infrastructure. Domain modules remain isolated and communicate through explicit service calls or events.
