# Phase 3: PrepAccess Auth, IAM, RBAC

## Goal

Add the identity and authorization foundation for PrepSuite tenants. PrepAccess now owns user accounts, password security, JWT access tokens, refresh token rotation, login history, invitations, custom roles, permission bindings, and permission dependencies for later modules.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `users` | Tenant-scoped or platform user accounts. | Optional `tenant_id -> tenants.id`. |
| `user_profiles` | Display/profile data for a user. | `user_id -> users.id`, optional `tenant_id`. |
| `permissions` | Global permission catalog using `app.resource.action`. | Referenced by `role_permissions`. |
| `roles` | Tenant custom/system roles or nullable platform roles. | Optional `tenant_id -> tenants.id`. |
| `role_permissions` | Role-to-permission bindings. | `role_id -> roles.id`, `permission_id -> permissions.id`. |
| `user_roles` | User-to-role assignments. | `user_id -> users.id`, `role_id -> roles.id`. |
| `refresh_tokens` | Hashed refresh token family records. | `user_id -> users.id`, family and parent rotation fields. |
| `login_sessions` | Session metadata tied to refresh tokens. | `user_id -> users.id`, optional `refresh_token_id`. |
| `login_history` | Success/failure login audit trail. | Optional `user_id -> users.id`. |
| `password_reset_tokens` | Hashed password reset tokens with expiry and usage. | `user_id -> users.id`. |
| `invitation_tokens` | Hashed tenant invitation tokens. | `tenant_id -> tenants.id`, optional `role_id -> roles.id`. |

`tenant_users.user_id` is now a foreign key to `users.id`. The previous placeholder membership bridge becomes the tenant membership index used by tenant resolution.

## Classes and Methods

- `AccessService.register_institution_admin`: validates tenant, seeds default permissions/system admin role, creates the admin user/profile/membership, assigns role, and returns tokens.
- `AccessService.login`: rate-limits failures, verifies Argon2 password hash, records login history, updates `last_login_at`, creates refresh token/session, and returns tokens.
- `AccessService.refresh`: sets RLS scope from the refresh token prefix, validates token hash/status/expiry, rotates the token, and detects token reuse.
- `AccessService.logout`: revokes one refresh token or all active user refresh tokens.
- `AccessService.request_password_reset` and `confirm_password_reset`: create hashed reset tokens, reset password, and revoke existing refresh tokens.
- `AccessService.invite_user` and `accept_invitation`: create scoped invitation tokens and onboard invited users.
- `AccessService.create_custom_role`, `assign_role_to_user`, `remove_role_from_user`: manage tenant RBAC.
- `AccessService.permission_matrix` and `current_permissions`: expose the catalog and effective user permissions.
- `get_current_user` and `get_current_principal`: decode RS256 JWTs, set RLS tenant/user context, fetch the active user, and load permissions.
- `require_permission("app.resource.action")`: rejects requests without the required permission.

Repositories keep SQLAlchemy query details only. Services own transaction boundaries, token workflows, RLS context setup, and business rules.

## API Endpoints

- `POST /api/v1/access/register-institution-admin`
- `POST /api/v1/access/login`
- `POST /api/v1/access/refresh`
- `POST /api/v1/access/logout`
- `POST /api/v1/access/password-reset/request`
- `POST /api/v1/access/password-reset/confirm`
- `POST /api/v1/access/invitations`
- `POST /api/v1/access/invitations/accept`
- `POST /api/v1/access/roles`
- `POST /api/v1/access/users/{user_id}/roles`
- `DELETE /api/v1/access/users/{user_id}/roles/{role_id}`
- `GET /api/v1/access/permission-matrix`
- `GET /api/v1/access/me`
- `GET /api/v1/access/me/permissions`

OpenAPI names use the `prepaccess:*` pattern for stable client generation.

## Security Contract

- Passwords are hashed with Argon2.
- Access tokens are RS256 JWTs with issuer, audience, subject, optional tenant ID, user type, expiry, and `jti`.
- Local/test environments generate an ephemeral RS256 key pair if PEM keys are not provided.
- Refresh, reset, and invitation tokens are stored as SHA-256 hashes only.
- Refresh token families detect reuse and revoke the family on replay.
- Login failures are rate-limited in-process for the bootstrap phase.
- Tenant-owned auth tables use PostgreSQL RLS. Scoped raw token prefixes let the app set `app.current_tenant_id` and `app.current_user_id` before hashed-token lookup.

## Tests

Phase 3 adds API integration tests for registration, login, JWT claims, current user, current permissions, permission matrix, login history, refresh rotation/reuse detection, invitation acceptance, permission denial, password reset, and login rate limiting.

Run:

```bash
make check
```

## Local Review

```bash
uv sync --all-groups
uv run alembic upgrade head
make check
docker compose up --build
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
curl http://localhost:8000/docs
```

Minimal manual flow:

1. Create a tenant through `POST /api/v1/platform/tenants`.
2. Register its admin through `POST /api/v1/access/register-institution-admin`.
3. Call `GET /api/v1/access/me` with the returned bearer token.
4. Call `GET /api/v1/access/me/permissions` and verify `prepaccess.role.manage` is present.
