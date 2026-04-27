# Database

Phase 1 configures SQLAlchemy 2.x async ORM and Alembic without domain tables.

## Connection

The API reads `PREPSUITE_DATABASE_URL`, defaulting to:

```text
postgresql+asyncpg://prepsuite:prepsuite@localhost:5432/prepsuite
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

The initial revision is a no-op bootstrap migration. Tenant tables and RLS helpers arrive in Phase 2.
