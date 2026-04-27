# API Baseline

All public endpoints are versioned under `/api/v1`.

## System Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness check for the API process. |
| `GET` | `/api/v1/ready` | Readiness check for PostgreSQL and Redis dependencies. |
| `GET` | `/api/v1/openapi.json` | OpenAPI schema. |

## Tenancy Endpoints

Platform bootstrap endpoints remain available for local bootstrapping until the platform-admin hardening phase wires them to PrepAccess platform permissions.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/platform/tenants` | Create a tenant institution with default settings and branding. |
| `GET` | `/api/v1/platform/tenants/{tenant_id}` | Fetch a tenant by ID. |
| `POST` | `/api/v1/platform/tenants/{tenant_id}/domains` | Add a tenant domain. |
| `GET` | `/api/v1/platform/app-catalog` | List app catalog entries. |
| `POST` | `/api/v1/platform/app-catalog` | Upsert one app catalog entry. |
| `POST` | `/api/v1/platform/app-catalog/seed` | Seed the default PrepSuite app catalog. |
| `PUT` | `/api/v1/platform/tenants/{tenant_id}/apps/{app_code}` | Update app enablement and subscription state. |
| `POST` | `/api/v1/platform/tenants/{tenant_id}/users` | Link an existing PrepAccess user UUID to a tenant. |
| `GET` | `/api/v1/tenant/current` | Resolve the current tenant context. |
| `GET` | `/api/v1/tenant/apps` | List apps visible to the current tenant. |
| `GET` | `/api/v1/tenant/settings` | Fetch current tenant settings. |
| `PATCH` | `/api/v1/tenant/settings` | Update current tenant settings. |
| `GET` | `/api/v1/tenant/branding` | Fetch current tenant branding. |
| `PATCH` | `/api/v1/tenant/branding` | Update current tenant branding. |

Tenant resolution supports `X-Tenant-ID`, `X-Tenant-Slug`, `X-Tenant-Domain`, host/domain, subdomain, `X-User-ID`, and authenticated JWT claims.

## PrepAccess Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/access/register-institution-admin` | Register the primary institution admin for an existing tenant. |
| `POST` | `/api/v1/access/login` | Authenticate with email/password and issue access/refresh tokens. |
| `POST` | `/api/v1/access/refresh` | Rotate a refresh token and issue a new token pair. |
| `POST` | `/api/v1/access/logout` | Revoke the current refresh token or all sessions. |
| `POST` | `/api/v1/access/password-reset/request` | Create a password reset token. Local/test responses expose the token until notification delivery exists. |
| `POST` | `/api/v1/access/password-reset/confirm` | Reset password and revoke active refresh tokens. |
| `POST` | `/api/v1/access/invitations` | Invite a tenant user. Requires `prepaccess.user.invite`. |
| `POST` | `/api/v1/access/invitations/accept` | Accept an invitation and create the invited user. |
| `POST` | `/api/v1/access/roles` | Create a custom tenant role. Requires `prepaccess.role.manage`. |
| `POST` | `/api/v1/access/users/{user_id}/roles` | Assign a role to a user. Requires `prepaccess.role.manage`. |
| `DELETE` | `/api/v1/access/users/{user_id}/roles/{role_id}` | Remove a user role. Requires `prepaccess.role.manage`. |
| `GET` | `/api/v1/access/permission-matrix` | List permissions and tenant roles. Requires `prepaccess.permission.read`. |
| `GET` | `/api/v1/access/me` | Return the authenticated user. |
| `GET` | `/api/v1/access/me/permissions` | Return the authenticated user's effective permission codes. |

Authenticated endpoints use `Authorization: Bearer <access_token>`. Access tokens are RS256 JWTs with `sub`, optional `tid`, `user_type`, `typ=access`, issuer, audience, expiry, and `jti`.

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
