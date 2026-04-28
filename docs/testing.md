# Testing

Phase 1 uses Pytest, pytest-asyncio, HTTPX ASGI transport, Ruff, and Mypy.

## Commands

```bash
make lint
make typecheck
make test
make check
```

## Coverage

Bootstrap tests verify:

- Health endpoint behavior.
- Readiness endpoint success and failure behavior.
- Request ID propagation.
- Standard error envelope.
- Settings defaults.
- Async SQLAlchemy engine and session factory construction.

Phase 2 adds Testcontainers-backed PostgreSQL tests for:

- Tenant context resolution by header, slug, domain, subdomain, and user membership.
- Tenant settings and app subscription scoping.
- Standard tenant-required errors.
- PostgreSQL RLS hiding rows without `app.current_tenant_id`.
- PostgreSQL RLS limiting reads to the current tenant.
- PostgreSQL RLS blocking writes for another tenant.

Phase 3 adds PrepAccess tests for:

- Institution-admin registration and JWT claim validation.
- Current user and current permission endpoints.
- Permission matrix access.
- Login history persistence under tenant RLS.
- Refresh token rotation and reuse detection.
- Invitation acceptance and permission denial for users without roles.
- Password reset confirmation.
- Login rate limiting.

Phase 4 adds PrepSettings tests for:

- General settings, branding, grading rules, and attendance rules.
- Audit event emission for settings writes.
- App toggles respecting subscription state and locked apps.
- Academic-year current flag exclusivity.
- Permission denial for users without `prepsettings.settings.manage`.

Phase 5 adds PrepStudents tests for:

- Student create/list/search/update/profile/timeline/soft delete.
- Duplicate tenant admission numbers.
- Guardian, note, document metadata, and enrollment creation.
- Bulk import partial success with duplicate payload reporting.
- Batch creation, capacity enforcement, membership removal, and filtered student listing.
- Disabled app rejection, permission denial for users without a role, and cross-tenant student isolation.

Phase 6 adds PrepPeople tests for:

- Department creation and employee directory filtering.
- Employee creation with optional PrepAccess user link and profile data.
- Duplicate employee-code conflict handling.
- Employee status updates, profile upsert, notes, document metadata, timeline, and aggregate profile.
- Teacher assignment creation, teacher workload summary, and non-teacher assignment rejection.
- Disabled app rejection, permission denial for users without a role, and cross-tenant employee isolation.

Phase 7 adds PrepLearn tests for:

- Course creation, tenant-unique slug conflict handling, list search, and draft filtering.
- Publish requirement failures for empty courses and modules without lessons.
- Module and lesson creation with automatic ordering.
- Curriculum reorder behavior for modules and lessons.
- Course assignment to PrepStudents batches and PrepPeople teachers.
- Publish, archive, and archived-publish rejection workflows.
- Student-facing outline response.
- Disabled app rejection, permission denial for users without a role, and cross-tenant course isolation.

Phase 8 adds PrepQuestion tests for:

- Topic creation and duplicate slug conflict handling.
- Question option validation for MCQ correctness rules.
- Question creation with metadata, options, and normalized tags.
- Question status workflow from draft to reviewed to approved.
- Question filtering by search, status, and tag.
- Question-set creation, item add, duplicate prevention, aggregate marks/distributions, and reorder.
- AI generation placeholder job creation and selected candidate approval.
- Disabled app rejection, permission denial for users without a role, and cross-tenant question isolation.

Phase 9 adds PrepAssess tests for:

- Assessment creation from a PrepQuestion question set.
- Cursor list filtering by search and status.
- Scheduling, publishing, attempt start, and attempt idempotency.
- Idempotent answer submission and replay.
- MCQ auto-evaluation and manual short-answer evaluation.
- Evaluation queue, result publishing, and assessment analytics.
- Disabled app rejection, permission denial for users without a role, and cross-tenant assessment isolation.

Phase 10 adds PrepAttend tests for:

- Student attendance session creation and bulk record marking.
- Student attendance summaries by batch and student.
- Student correction request creation, approval, and approved-status application.
- Employee check-in idempotency, check-out, summary counts, and work seconds.
- Disabled app rejection, permission denial for users without a role, and cross-tenant attendance isolation.

Phase 11 adds PrepLive tests for:

- Live class scheduling and generated link shape.
- Class list/detail/by-code reads.
- Open/end state transitions.
- Student access validation for batch members.
- Capacity enforcement and join-window expiry denial.
- Non-member student denial and unassigned teacher scheduling rejection.
- Attendance event capture and recording metadata creation.
- Disabled app rejection, permission denial for users without a role, and cross-tenant live class isolation.

The PostgreSQL Testcontainers fixture now lives at `tests/conftest.py` and is shared across module tests. Each integration test truncates all current Phase 1-11 tables from the owner connection, then exercises the API through the non-superuser app role.

Future phases will extend this setup for feature gates, workers, and live flows.
