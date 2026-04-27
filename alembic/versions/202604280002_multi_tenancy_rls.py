"""multi tenancy and rls

Revision ID: 202604280002
Revises: 202604280001
Create Date: 2026-04-28 01:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280002"
down_revision: str | None = "202604280001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_OWNED_TABLES = (
    "tenant_apps",
    "tenant_settings",
    "tenant_branding",
    "tenant_users",
)

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)
USER_POLICY_EXPRESSION = "user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table_name}_tenant_isolation
        ON {table_name}
        USING ({TENANT_POLICY_EXPRESSION})
        WITH CHECK ({TENANT_POLICY_EXPRESSION})
        """
    )


def enable_tenant_domains_rls() -> None:
    op.execute("ALTER TABLE tenant_domains ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_domains FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_domains_public_resolution
        ON tenant_domains
        FOR SELECT
        USING (true)
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_domains_tenant_insert
        ON tenant_domains
        FOR INSERT
        WITH CHECK ({TENANT_POLICY_EXPRESSION})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_domains_tenant_update
        ON tenant_domains
        FOR UPDATE
        USING ({TENANT_POLICY_EXPRESSION})
        WITH CHECK ({TENANT_POLICY_EXPRESSION})
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_domains_tenant_delete
        ON tenant_domains
        FOR DELETE
        USING ({TENANT_POLICY_EXPRESSION})
        """
    )


def disable_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def disable_tenant_domains_rls() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_domains_tenant_delete ON tenant_domains")
    op.execute("DROP POLICY IF EXISTS tenant_domains_tenant_update ON tenant_domains")
    op.execute("DROP POLICY IF EXISTS tenant_domains_tenant_insert ON tenant_domains")
    op.execute("DROP POLICY IF EXISTS tenant_domains_public_resolution ON tenant_domains")
    op.execute("ALTER TABLE tenant_domains DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="trial", nullable=False),
        sa.Column("plan_type", sa.String(length=80), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_status", "tenants", ["status"])
    op.create_index(op.f("ix_tenants_deleted_at"), "tenants", ["deleted_at"])

    op.create_table(
        "app_catalog",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("is_core", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_catalog")),
        sa.UniqueConstraint("code", name="uq_app_catalog_code"),
    )
    op.create_index("ix_app_catalog_category", "app_catalog", ["category"])

    op.create_table(
        "tenant_domains",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column(
            "verification_status", sa.String(length=32), server_default="pending", nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_domains_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_domains")),
        sa.UniqueConstraint("domain", name="uq_tenant_domains_domain"),
        sa.UniqueConstraint("tenant_id", "domain", name="uq_tenant_domains_tenant_id_domain"),
    )
    op.create_index(op.f("ix_tenant_domains_tenant_id"), "tenant_domains", ["tenant_id"])
    op.create_index(
        "ix_tenant_domains_tenant_primary", "tenant_domains", ["tenant_id", "is_primary"]
    )

    op.create_table(
        "tenant_apps",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("app_code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="disabled", nullable=False),
        sa.Column(
            "subscription_status", sa.String(length=32), server_default="trial", nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["app_code"],
            ["app_catalog.code"],
            name=op.f("fk_tenant_apps_app_code_app_catalog"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_apps_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_apps")),
        sa.UniqueConstraint("tenant_id", "app_code", name="uq_tenant_apps_tenant_id_app_code"),
    )
    op.create_index(op.f("ix_tenant_apps_tenant_id"), "tenant_apps", ["tenant_id"])
    op.create_index("ix_tenant_apps_tenant_status", "tenant_apps", ["tenant_id", "status"])

    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timezone", sa.String(length=80), server_default="UTC", nullable=False),
        sa.Column("locale", sa.String(length=16), server_default="en", nullable=False),
        sa.Column(
            "general_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "notification_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_settings_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_settings")),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant_id"),
    )
    op.create_index(op.f("ix_tenant_settings_tenant_id"), "tenant_settings", ["tenant_id"])

    op.create_table(
        "tenant_branding",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=32), nullable=True),
        sa.Column("secondary_color", sa.String(length=32), nullable=True),
        sa.Column("accent_color", sa.String(length=32), nullable=True),
        sa.Column(
            "branding_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_branding_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_branding")),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_branding_tenant_id"),
    )
    op.create_index(op.f("ix_tenant_branding_tenant_id"), "tenant_branding", ["tenant_id"])

    op.create_table(
        "tenant_users",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("is_primary_admin", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tenant_users_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_users")),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_id_user_id"),
    )
    op.create_index(op.f("ix_tenant_users_tenant_id"), "tenant_users", ["tenant_id"])
    op.create_index("ix_tenant_users_user_id", "tenant_users", ["user_id"])

    enable_tenant_domains_rls()
    for table_name in TENANT_OWNED_TABLES:
        enable_rls(table_name)
    op.execute(
        f"""
        CREATE POLICY tenant_users_self_resolution
        ON tenant_users
        FOR SELECT
        USING ({USER_POLICY_EXPRESSION})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_users_self_resolution ON tenant_users")
    for table_name in reversed(TENANT_OWNED_TABLES):
        disable_rls(table_name)
    disable_tenant_domains_rls()

    op.drop_index("ix_tenant_users_user_id", table_name="tenant_users")
    op.drop_index(op.f("ix_tenant_users_tenant_id"), table_name="tenant_users")
    op.drop_table("tenant_users")
    op.drop_index(op.f("ix_tenant_branding_tenant_id"), table_name="tenant_branding")
    op.drop_table("tenant_branding")
    op.drop_index(op.f("ix_tenant_settings_tenant_id"), table_name="tenant_settings")
    op.drop_table("tenant_settings")
    op.drop_index("ix_tenant_apps_tenant_status", table_name="tenant_apps")
    op.drop_index(op.f("ix_tenant_apps_tenant_id"), table_name="tenant_apps")
    op.drop_table("tenant_apps")
    op.drop_index("ix_tenant_domains_tenant_primary", table_name="tenant_domains")
    op.drop_index(op.f("ix_tenant_domains_tenant_id"), table_name="tenant_domains")
    op.drop_table("tenant_domains")
    op.drop_index("ix_app_catalog_category", table_name="app_catalog")
    op.drop_table("app_catalog")
    op.drop_index(op.f("ix_tenants_deleted_at"), table_name="tenants")
    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_table("tenants")
