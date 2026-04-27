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

The PostgreSQL Testcontainers fixture now lives at `tests/conftest.py` and is shared across module tests. Each integration test truncates all current Phase 1-5 tables from the owner connection, then exercises the API through the non-superuser app role.

Future phases will extend this setup for feature gates, workers, and live flows.
