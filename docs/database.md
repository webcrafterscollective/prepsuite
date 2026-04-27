# Database

Phase 1 configures SQLAlchemy 2.x async ORM and Alembic. Phase 2 adds the tenant foundation and PostgreSQL RLS. Phase 3 adds PrepAccess identity, RBAC, and auth-token tables.

## Connection

The API reads `PREPSUITE_DATABASE_URL`, defaulting to the non-superuser app role:

```text
postgresql+asyncpg://prepsuite_app:prepsuite_app@localhost:5432/prepsuite
```

Alembic reads `PREPSUITE_MIGRATION_DATABASE_URL`, defaulting to the owner role:

```text
postgresql+asyncpg://prepsuite_owner:prepsuite_owner@localhost:5432/prepsuite
```

## Shared Model Base

`app/shared/models.py` defines:

- `Base`: SQLAlchemy declarative base with naming conventions.
- `UUIDPrimaryKeyMixin`: UUID primary key helper.
- `TimestampMixin`: `created_at` and `updated_at` columns.

## Migrations

Run migrations with:

```bash
make migrate
```

The initial revision is a no-op bootstrap migration. The Phase 2 revision creates:

- `tenants`
- `tenant_domains`
- `app_catalog`
- `tenant_apps`
- `tenant_settings`
- `tenant_branding`
- `tenant_users`

The Phase 3 revision creates:

- `users`
- `user_profiles`
- `permissions`
- `roles`
- `role_permissions`
- `user_roles`
- `refresh_tokens`
- `login_sessions`
- `login_history`
- `password_reset_tokens`
- `invitation_tokens`

It also adds `tenant_users.user_id -> users.id`.

RLS is enabled and forced on tenant-owned tables. The policy pattern is:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`tenant_domains` allows public SELECT for domain resolution but enforces tenant-scoped writes. `tenant_users` adds a self-resolution SELECT policy based on `app.current_user_id`.

PrepAccess tenant-owned auth tables use the same tenant setting, with self-access policies where token/session lookup needs `app.current_user_id`. Refresh, reset, and invitation tokens are stored only as SHA-256 hashes; their raw values include a tenant/user scope prefix so the application can set RLS context before querying the hash.
