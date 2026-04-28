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

## Phase 4 Components

- `app/modules/settings/models.py`: academic years, grading rules, attendance rules, integrations, and per-app tenant settings.
- `app/modules/settings/service.py`: general/branding updates, subscription-aware app toggles, academic year workflows, default grading/attendance rules, and audit event emission.
- `app/modules/settings/router.py`: `/settings/*` API surface protected by `prepsettings.settings.manage`.
- `app/core/events.py`: in-process event dispatcher singleton used by PrepSettings audit events until the transactional outbox lands.

## Phase 5 Components

- `app/modules/students/models.py`: students, guardians, student links, batches, batch memberships, enrollments, notes, documents, and status history.
- `app/modules/students/repository.py`: tenant-scoped SQLAlchemy queries, cursor pagination, batch capacity counts, and profile eager loading.
- `app/modules/students/service.py`: student lifecycle, bulk import, soft delete, status history, guardian/document/note/enrollment workflows, batch assignment, and student profile/timeline aggregation.
- `app/modules/students/router.py`: `/students/*` and `/batches/*` API surface protected by the `prepstudents` feature gate and PrepStudents RBAC permissions.
- `alembic/versions/202604280005_prep_students.py`: table creation plus forced PostgreSQL RLS policies for every tenant-owned PrepStudents table.

## Phase 6 Components

- `app/modules/people/models.py`: departments, employees, employee profiles, employee documents, notes, status history, and teacher assignments.
- `app/modules/people/repository.py`: tenant-scoped employee directory queries, cursor pagination, department lookup, profile eager loading, and teacher assignment summaries.
- `app/modules/people/service.py`: department creation, employee lifecycle, staff-user linking, profile upsert, status history, teacher-only assignment validation, workload aggregation, and employee profile/timeline aggregation.
- `app/modules/people/router.py`: `/people/*` API surface protected by the `preppeople` feature gate and PrepPeople RBAC permissions.
- `alembic/versions/202604280006_prep_people.py`: table creation plus forced PostgreSQL RLS policies for every tenant-owned PrepPeople table.

## Phase 7 Components

- `app/modules/learn/models.py`: courses, modules, lessons, lesson resources, course-batch assignments, course-teacher assignments, publish history, and course prerequisites.
- `app/modules/learn/repository.py`: tenant-scoped curriculum queries, cursor pagination, course detail eager loading, order-index helpers, and assignment lookups.
- `app/modules/learn/service.py`: course lifecycle, module/lesson workflows, publishing rules, safe curriculum reordering, batch/teacher assignment validation, and course outline/detail aggregation.
- `app/modules/learn/router.py`: `/learn/*` API surface protected by the `preplearn` feature gate and PrepLearn RBAC permissions.
- `alembic/versions/202604280007_prep_learn.py`: table creation plus forced PostgreSQL RLS policies for every tenant-owned PrepLearn table.

## Phase 8 Components

- `app/modules/question/models.py`: question topics, questions, options, tags, question sets, set items, and AI generation jobs.
- `app/modules/question/repository.py`: tenant-scoped question-bank queries, cursor pagination, topic lookup, question-set detail eager loading, and set-item ordering helpers.
- `app/modules/question/service.py`: topic management, question validation, approval workflow, option/tag replacement, set builder logic, AI placeholder generation, generated-question approval, and event emission.
- `app/modules/question/router.py`: `/questions/*` and `/question-sets/*` API surface protected by the `prepquestion` feature gate and PrepQuestion RBAC permissions.
- `alembic/versions/202604280008_prep_question.py`: table creation plus forced PostgreSQL RLS policies for every tenant-owned PrepQuestion table.

## Clean Architecture Rules

Routers orchestrate HTTP concerns only. Services own business workflows. Repositories own persistence queries. Core dependencies expose infrastructure. Domain modules remain isolated and communicate through explicit service calls or events.

The database role split is part of the architecture: Alembic migrations run as an owner role, while the API connects as a non-superuser app role so PostgreSQL RLS is actually enforced.

PrepAccess follows the same boundary rule: routers never inspect password hashes, token families, or role bindings directly; services enforce workflows and repositories keep SQLAlchemy queries only.

PrepSettings reuses the tenancy-owned `tenant_settings`, `tenant_branding`, `tenant_apps`, and `app_catalog` models where those are already the source of truth, while keeping module-specific tables in the settings bounded context.

PrepStudents keeps route handlers intentionally thin: routers inject tenant context, current principal, permissions, and tenant-scoped sessions; services enforce app workflow rules and publish domain events; repositories contain only query and persistence helpers. Course references remain UUID-only until PrepLearn lands, keeping Phase 5 decoupled from future curriculum tables.

PrepPeople follows the same boundary. The service validates optional PrepAccess `user_id` links and optional PrepStudents `batch_id` links, while `course_id` remains UUID-only until PrepLearn lands. Teacher workload rules live in the service layer, not the router or repository.

PrepLearn now owns course UUIDs and curriculum structure. PrepStudents and PrepPeople remain decoupled through explicit assignment tables: batch ownership is validated against PrepStudents, teacher ownership is validated against PrepPeople, and route handlers still never reach across bounded contexts directly. PrepLearn service methods assemble read DTOs before committing when PostgreSQL RLS transaction-local tenant settings would otherwise be cleared.

PrepQuestion follows the same boundary. Question-set calculations and AI placeholder workflows live in the service layer; repositories never make permission or workflow decisions. The AI generation provider is an interface-first placeholder, so a real provider can be introduced later without changing API contracts or persistence ownership.
