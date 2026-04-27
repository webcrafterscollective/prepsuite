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

## Phase 3 Components

- `app/modules/access/models.py`: users, profiles, roles, permissions, role/user bindings, refresh tokens, sessions, login history, resets, and invitations.
- `app/modules/access/service.py`: registration, login, refresh rotation, logout, password reset, invitations, role assignment, and permission matrix use cases.
- `app/modules/access/dependencies.py`: JWT bearer authentication, current user, current principal, and request metadata dependencies.
- `app/core/security.py`: Argon2 password hashing, RS256 access token creation/validation, refresh-token hashing helpers, and ephemeral local keys when env keys are absent.
- `app/core/permissions.py`: `require_permission("app.resource.action")` dependency used by routers.

## Clean Architecture Rules

Routers orchestrate HTTP concerns only. Services own business workflows. Repositories own persistence queries. Core dependencies expose infrastructure. Domain modules remain isolated and communicate through explicit service calls or events.

The database role split is part of the architecture: Alembic migrations run as an owner role, while the API connects as a non-superuser app role so PostgreSQL RLS is actually enforced.

PrepAccess follows the same boundary rule: routers never inspect password hashes, token families, or role bindings directly; services enforce workflows and repositories keep SQLAlchemy queries only.
