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

Future phases will extend this setup for permissions, feature gates, workers, and live flows.
