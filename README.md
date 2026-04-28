# PrepSuite Backend

PrepSuite is a production-grade, multi-tenant learning management SaaS backend. The current backend includes the service bootstrap, PostgreSQL RLS tenant foundation, PrepAccess authentication/RBAC, PrepSettings, student lifecycle, employee/teacher operations, PrepLearn curriculum management, and PrepQuestion question-bank workflows.

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

## Phase Status

Phase 1 establishes the clean architecture skeleton, async database setup, Alembic, Redis readiness checks, Celery shell, Docker services, structured logging, request IDs, CORS, error handling, and baseline tests.

Phase 2 adds the multi-tenancy foundation: tenant records, tenant domains, app catalog, tenant app subscriptions, tenant settings, tenant branding, tenant users, PostgreSQL RLS policies, tenant resolution, and tenant-scoped sessions.

Phase 3 adds PrepAccess: institution-admin registration, Argon2 password hashing, RS256 JWT access tokens, refresh token rotation/reuse detection, login sessions/history, password resets, invitations, roles, permissions, and permission dependencies.

Phase 4 adds PrepSettings: tenant general settings, branding, subscription-aware app toggles, academic years, grading rules, attendance rules, integration/app settings tables, and settings audit events.

Phase 5 adds PrepStudents: student records, guardians, batches, enrollments, notes, document metadata, status history, profile/timeline aggregates, bulk import, cursor pagination, app gates, RBAC, and RLS-backed tenant isolation.

Phase 6 adds PrepPeople: departments, employees, employee profiles, staff document metadata, employee notes/status history, teacher assignments, teacher workload summaries, staff-user linking, app gates, RBAC, and RLS-backed tenant isolation.

Phase 7 adds PrepLearn: courses, modules, lessons, lesson resources, course-batch mappings, course-teacher mappings, publish history, prerequisites, curriculum ordering, publishing rules, app gates, RBAC, and RLS-backed tenant isolation.

Phase 8 adds PrepQuestion: question topics, question bank records, options, tags, question sets, set-item ordering, AI generation job metadata with placeholder generation, review/approval flows, app gates, RBAC, and RLS-backed tenant isolation.

See `docs/phase-01-bootstrap.md` for the implementation map and review checklist.
See `docs/phase-02-multi-tenancy-rls.md` for the tenancy model, API, and RLS contract.
See `docs/phase-03-prepaccess-auth-rbac.md` for the authentication and RBAC contract.
See `docs/phase-04-prepsettings.md` for the settings data model, APIs, and app toggle rules.
See `docs/phase-05-prepstudents.md` for the student lifecycle model, APIs, and test coverage.
See `docs/phase-06-preppeople.md` for the employee/teacher operations model, APIs, and test coverage.
See `docs/phase-07-preplearn.md` for the curriculum model, APIs, and test coverage.
See `docs/phase-08-prepquestion.md` for the question-bank model, APIs, and test coverage.
