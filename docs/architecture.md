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

## Phase 2 Components

- `app/modules/tenancy/models.py`: tenant, domain, app catalog, app subscription, settings, branding, and membership tables.
- `app/modules/tenancy/service.py`: tenant creation, resolution, app catalog seeding, app subscription gates, and scoped settings/branding use cases.
- `app/modules/tenancy/dependencies.py`: FastAPI tenant resolution and tenant-scoped DB session dependencies.
- `app/core/tenant_context.py`: tenant context value object, app-layer guard, and `set_config` helpers for PostgreSQL RLS.
- `app/core/feature_gates.py`: `require_app_enabled("app_code")` dependency backed by `tenant_apps`.

## Clean Architecture Rules

Routers orchestrate HTTP concerns only. Services own business workflows. Repositories own persistence queries. Core dependencies expose infrastructure. Domain modules remain isolated and communicate through explicit service calls or events.

The database role split is part of the architecture: Alembic migrations run as an owner role, while the API connects as a non-superuser app role so PostgreSQL RLS is actually enforced.
