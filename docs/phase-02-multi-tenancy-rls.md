# Phase 2: Multi-Tenancy + RLS

## Goal

Establish tenant isolation for PrepSuite institutions before any business modules are added. Every future tenant-owned module will reuse the tenant context dependency, app-layer guard, and PostgreSQL RLS pattern introduced here.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `tenants` | Institution root record. | Parent for tenant-owned setup tables. |
| `tenant_domains` | Custom domains and host-based resolution. | `tenant_id -> tenants.id`; public SELECT for resolution, scoped writes. |
| `app_catalog` | Global PrepSuite app registry. | Referenced by `tenant_apps.app_code`. |
| `tenant_apps` | Tenant app enablement and subscription state. | `tenant_id -> tenants.id`, `app_code -> app_catalog.code`. |
| `tenant_settings` | General tenant settings. | One row per tenant. |
| `tenant_branding` | Branding and theme settings. | One row per tenant. |
| `tenant_users` | Temporary user-to-tenant membership bridge until PrepAccess. | `tenant_id -> tenants.id`; `user_id` becomes a users FK in Phase 3. |

Enums are stored as strings for simple migrations and Pydantic/OpenAPI clarity: tenant status, domain verification status, tenant app status, subscription status, and tenant user status.

## Classes and Methods

- `TenantContext`: resolved tenant ID plus source (`header`, `subdomain`, `authenticated_user`, or `unresolved`).
- `set_current_tenant_in_session`: executes `SELECT set_config('app.current_tenant_id', tenant_id, true)`.
- `TenantService.create_tenant`: creates tenant, default settings, default branding, and optional primary domain.
- `TenantService.resolve_tenant`: resolves by tenant ID, slug, domain, subdomain, or user membership.
- `TenantService.upsert_tenant_app`: manages app subscription state for a tenant.
- `TenantService.is_app_enabled`: backs `require_app_enabled("app_code")`.
- Repositories keep SQLAlchemy queries only; services own validation, RLS setup, commits, and app-layer guards.

## API Endpoints

Platform bootstrap:

- `POST /api/v1/platform/tenants`
- `GET /api/v1/platform/tenants/{tenant_id}`
- `POST /api/v1/platform/tenants/{tenant_id}/domains`
- `GET /api/v1/platform/app-catalog`
- `POST /api/v1/platform/app-catalog`
- `POST /api/v1/platform/app-catalog/seed`
- `PUT /api/v1/platform/tenants/{tenant_id}/apps/{app_code}`
- `POST /api/v1/platform/tenants/{tenant_id}/users`

Tenant-scoped:

- `GET /api/v1/tenant/current`
- `GET /api/v1/tenant/apps`
- `GET /api/v1/tenant/settings`
- `PATCH /api/v1/tenant/settings`
- `GET /api/v1/tenant/branding`
- `PATCH /api/v1/tenant/branding`

## RLS Contract

The API must connect as `prepsuite_app`, not the owner/superuser role. Alembic uses `prepsuite_owner`. Tests prove this with a Testcontainers database and a non-superuser app role.

Tenant-owned reads/writes are scoped by `app.current_tenant_id`. Tenant user resolution additionally sets `app.current_user_id` and can only read that user's memberships. Custom domain lookup is intentionally public-read because tenant resolution must happen before a tenant ID is known.

## Local Review

```bash
uv sync --all-groups
uv run alembic upgrade head
make seed
make check
docker compose up --build
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
```

Seed the app catalog through HTTP:

```bash
curl -X POST http://localhost:8000/api/v1/platform/app-catalog/seed
```
