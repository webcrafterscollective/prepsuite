"""prep settings

Revision ID: 202604280004
Revises: 202604280003
Create Date: 2026-04-28 04:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280004"
down_revision: str | None = "202604280003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "tenant_academic_years",
    "tenant_grading_rules",
    "tenant_attendance_rules",
    "tenant_integrations",
    "tenant_app_settings",
)


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


def disable_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def grant_app_role() -> None:
    op.execute(
        """
        DO
        $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'prepsuite_app') THEN
                GRANT USAGE ON SCHEMA public TO prepsuite_app;
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO prepsuite_app;
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "tenant_academic_years",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_academic_years_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_academic_years")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tenant_academic_years_tenant_code"),
    )
    op.create_index(op.f("ix_tenant_academic_years_tenant_id"), "tenant_academic_years", ["tenant_id"])
    op.create_index(op.f("ix_tenant_academic_years_deleted_at"), "tenant_academic_years", ["deleted_at"])
    op.create_index("ix_tenant_academic_years_tenant_current", "tenant_academic_years", ["tenant_id", "is_current"])
    op.create_index("ix_tenant_academic_years_tenant_status", "tenant_academic_years", ["tenant_id", "status"])

    op.create_table(
        "tenant_grading_rules",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("grade_scale", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("pass_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("rounding_strategy", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_grading_rules_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_grading_rules")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tenant_grading_rules_tenant_code"),
    )
    op.create_index(op.f("ix_tenant_grading_rules_tenant_id"), "tenant_grading_rules", ["tenant_id"])
    op.create_index(op.f("ix_tenant_grading_rules_deleted_at"), "tenant_grading_rules", ["deleted_at"])
    op.create_index("ix_tenant_grading_rules_tenant_default", "tenant_grading_rules", ["tenant_id", "is_default"])

    op.create_table(
        "tenant_attendance_rules",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("minimum_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("late_threshold_minutes", sa.Integer(), nullable=True),
        sa.Column("absent_after_minutes", sa.Integer(), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_attendance_rules_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_attendance_rules")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tenant_attendance_rules_tenant_code"),
    )
    op.create_index(op.f("ix_tenant_attendance_rules_tenant_id"), "tenant_attendance_rules", ["tenant_id"])
    op.create_index(op.f("ix_tenant_attendance_rules_deleted_at"), "tenant_attendance_rules", ["deleted_at"])
    op.create_index("ix_tenant_attendance_rules_tenant_default", "tenant_attendance_rules", ["tenant_id", "is_default"])

    op.create_table(
        "tenant_integrations",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("integration_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="disabled", nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("secrets_ref", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_integrations_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_integrations")),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_tenant_integrations_tenant_provider"),
    )
    op.create_index(op.f("ix_tenant_integrations_tenant_id"), "tenant_integrations", ["tenant_id"])
    op.create_index(op.f("ix_tenant_integrations_deleted_at"), "tenant_integrations", ["deleted_at"])
    op.create_index("ix_tenant_integrations_tenant_type", "tenant_integrations", ["tenant_id", "integration_type"])

    op.create_table(
        "tenant_app_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("app_code", sa.String(length=80), nullable=False),
        sa.Column("enabled_by_tenant", sa.Boolean(), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["app_code"], ["app_catalog.code"], name=op.f("fk_tenant_app_settings_app_code_app_catalog"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_app_settings_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_app_settings")),
        sa.UniqueConstraint("tenant_id", "app_code", name="uq_tenant_app_settings_tenant_app"),
    )
    op.create_index(op.f("ix_tenant_app_settings_tenant_id"), "tenant_app_settings", ["tenant_id"])
    op.create_index("ix_tenant_app_settings_tenant_enabled", "tenant_app_settings", ["tenant_id", "enabled_by_tenant"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_tenant_app_settings_tenant_enabled", table_name="tenant_app_settings")
    op.drop_index(op.f("ix_tenant_app_settings_tenant_id"), table_name="tenant_app_settings")
    op.drop_table("tenant_app_settings")

    op.drop_index("ix_tenant_integrations_tenant_type", table_name="tenant_integrations")
    op.drop_index(op.f("ix_tenant_integrations_deleted_at"), table_name="tenant_integrations")
    op.drop_index(op.f("ix_tenant_integrations_tenant_id"), table_name="tenant_integrations")
    op.drop_table("tenant_integrations")

    op.drop_index("ix_tenant_attendance_rules_tenant_default", table_name="tenant_attendance_rules")
    op.drop_index(op.f("ix_tenant_attendance_rules_deleted_at"), table_name="tenant_attendance_rules")
    op.drop_index(op.f("ix_tenant_attendance_rules_tenant_id"), table_name="tenant_attendance_rules")
    op.drop_table("tenant_attendance_rules")

    op.drop_index("ix_tenant_grading_rules_tenant_default", table_name="tenant_grading_rules")
    op.drop_index(op.f("ix_tenant_grading_rules_deleted_at"), table_name="tenant_grading_rules")
    op.drop_index(op.f("ix_tenant_grading_rules_tenant_id"), table_name="tenant_grading_rules")
    op.drop_table("tenant_grading_rules")

    op.drop_index("ix_tenant_academic_years_tenant_status", table_name="tenant_academic_years")
    op.drop_index("ix_tenant_academic_years_tenant_current", table_name="tenant_academic_years")
    op.drop_index(op.f("ix_tenant_academic_years_deleted_at"), table_name="tenant_academic_years")
    op.drop_index(op.f("ix_tenant_academic_years_tenant_id"), table_name="tenant_academic_years")
    op.drop_table("tenant_academic_years")
