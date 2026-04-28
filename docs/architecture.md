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

## Phase 9 Components

- `app/modules/assess/models.py`: assessments, sections, assessment questions, attempts, answers, evaluations, results, assignment submissions, and evaluation comments.
- `app/modules/assess/repository.py`: tenant-scoped assessment queries, cursor pagination, eager-loaded detail reads, attempt lookup, answer lookup, pending evaluation queue, and result lookup.
- `app/modules/assess/service.py`: assessment creation from question sets, scheduling, publishing, attempt timing and student-access checks, idempotent answer submission, MCQ auto-evaluation, manual evaluation, result publishing, analytics, and event emission.
- `app/modules/assess/router.py`: `/assessments/*` and `/assessment-*/*` API surface protected by the `prepassess` feature gate and PrepAssess RBAC permissions.
- `alembic/versions/202604280009_prep_assess.py`: table creation plus forced PostgreSQL RLS policies for every tenant-owned PrepAssess table.

## Phase 10 Components

- `app/modules/attend/models.py`: student attendance sessions, student records, employee records, correction requests, and attendance policies.
- `app/modules/attend/repository.py`: tenant-scoped lookups for sessions, records, summaries, employee daily records, corrections, and policies.
- `app/modules/attend/service.py`: batch/student/employee ownership validation, bulk student marking, employee check-in/out idempotency, summary aggregation, correction approval, and event emission.
- `app/modules/attend/router.py`: `/attend/*` API surface protected by the `prepattend` feature gate and PrepAttend RBAC permissions.
- `alembic/versions/202604280010_prep_attend.py`: table creation plus forced PostgreSQL RLS policies for every tenant-owned PrepAttend table.

## Clean Architecture Rules

Routers orchestrate HTTP concerns only. Services own business workflows. Repositories own persistence queries. Core dependencies expose infrastructure. Domain modules remain isolated and communicate through explicit service calls or events.

The database role split is part of the architecture: Alembic migrations run as an owner role, while the API connects as a non-superuser app role so PostgreSQL RLS is actually enforced.

PrepAccess follows the same boundary rule: routers never inspect password hashes, token families, or role bindings directly; services enforce workflows and repositories keep SQLAlchemy queries only.

PrepSettings reuses the tenancy-owned `tenant_settings`, `tenant_branding`, `tenant_apps`, and `app_catalog` models where those are already the source of truth, while keeping module-specific tables in the settings bounded context.

PrepStudents keeps route handlers intentionally thin: routers inject tenant context, current principal, permissions, and tenant-scoped sessions; services enforce app workflow rules and publish domain events; repositories contain only query and persistence helpers. Course references remain UUID-only until PrepLearn lands, keeping Phase 5 decoupled from future curriculum tables.

PrepPeople follows the same boundary. The service validates optional PrepAccess `user_id` links and optional PrepStudents `batch_id` links, while `course_id` remains UUID-only until PrepLearn lands. Teacher workload rules live in the service layer, not the router or repository.

PrepLearn now owns course UUIDs and curriculum structure. PrepStudents and PrepPeople remain decoupled through explicit assignment tables: batch ownership is validated against PrepStudents, teacher ownership is validated against PrepPeople, and route handlers still never reach across bounded contexts directly. PrepLearn service methods assemble read DTOs before committing when PostgreSQL RLS transaction-local tenant settings would otherwise be cleared.

PrepQuestion follows the same boundary. Question-set calculations and AI placeholder workflows live in the service layer; repositories never make permission or workflow decisions. The AI generation provider is an interface-first placeholder, so a real provider can be introduced later without changing API contracts or persistence ownership.

PrepAssess is the first module that composes two mature bounded contexts. It reads PrepQuestion question sets/questions to snapshot assessment questions, validates optional PrepStudents batch/student ownership, and keeps assessment workflow state inside the assess context. Attempt timing, idempotency, scoring, and result-publication rules stay in the service layer. Repositories remain SQL-only, and routers continue to expose dependency injection, permission checks, and OpenAPI-friendly endpoint names.

PrepAttend composes PrepStudents and PrepPeople while owning operational attendance state. Student attendance validates active batch membership before records are marked. Employee attendance validates employee ownership before check-in/check-out writes. Correction requests are modeled as explicit workflow records so direct changes and approved corrections remain distinguishable for future audit integration.
