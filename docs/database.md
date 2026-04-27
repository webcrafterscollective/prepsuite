# Database

Phase 1 configures SQLAlchemy 2.x async ORM and Alembic. Phase 2 adds the tenant foundation and PostgreSQL RLS.

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

RLS is enabled and forced on tenant-owned tables. The policy pattern is:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`tenant_domains` allows public SELECT for domain resolution but enforces tenant-scoped writes. `tenant_users` adds a self-resolution SELECT policy based on `app.current_user_id`.
