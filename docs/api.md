# API Baseline

All public endpoints are versioned under `/api/v1`.

## System Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness check for the API process. |
| `GET` | `/api/v1/ready` | Readiness check for PostgreSQL and Redis dependencies. |
| `GET` | `/api/v1/openapi.json` | OpenAPI schema. |

## Tenancy Endpoints

Platform bootstrap endpoints are temporarily unauthenticated until PrepAccess is implemented in Phase 3.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/platform/tenants` | Create a tenant institution with default settings and branding. |
| `GET` | `/api/v1/platform/tenants/{tenant_id}` | Fetch a tenant by ID. |
| `POST` | `/api/v1/platform/tenants/{tenant_id}/domains` | Add a tenant domain. |
| `GET` | `/api/v1/platform/app-catalog` | List app catalog entries. |
| `POST` | `/api/v1/platform/app-catalog` | Upsert one app catalog entry. |
| `POST` | `/api/v1/platform/app-catalog/seed` | Seed the default PrepSuite app catalog. |
| `PUT` | `/api/v1/platform/tenants/{tenant_id}/apps/{app_code}` | Update app enablement and subscription state. |
| `POST` | `/api/v1/platform/tenants/{tenant_id}/users` | Link a user UUID to a tenant before PrepAccess lands. |
| `GET` | `/api/v1/tenant/current` | Resolve the current tenant context. |
| `GET` | `/api/v1/tenant/apps` | List apps visible to the current tenant. |
| `GET` | `/api/v1/tenant/settings` | Fetch current tenant settings. |
| `PATCH` | `/api/v1/tenant/settings` | Update current tenant settings. |
| `GET` | `/api/v1/tenant/branding` | Fetch current tenant branding. |
| `PATCH` | `/api/v1/tenant/branding` | Update current tenant branding. |

Tenant resolution currently supports `X-Tenant-ID`, `X-Tenant-Slug`, `X-Tenant-Domain`, host/domain, subdomain, and `X-User-ID`. JWT-backed resolution replaces the temporary user header in Phase 3.

## Error Shape

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {},
    "request_id": "string"
  }
}
```

Every response includes or propagates the `X-Request-ID` header.
