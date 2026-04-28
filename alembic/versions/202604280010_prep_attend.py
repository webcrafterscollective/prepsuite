"""prep attend

Revision ID: 202604280010
Revises: 202604280009
Create Date: 2026-04-28 10:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280010"
down_revision: str | None = "202604280009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "student_attendance_sessions",
    "attendance_policies",
    "student_attendance_records",
    "employee_attendance_records",
    "attendance_correction_requests",
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
        "student_attendance_sessions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("live_class_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("marked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_student_attendance_sessions_batch_id_batches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_student_attendance_sessions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_attendance_sessions")),
    )
    op.create_index(op.f("ix_student_attendance_sessions_tenant_id"), "student_attendance_sessions", ["tenant_id"])
    op.create_index("ix_student_attendance_sessions_tenant_batch", "student_attendance_sessions", ["tenant_id", "batch_id"])
    op.create_index("ix_student_attendance_sessions_tenant_date", "student_attendance_sessions", ["tenant_id", "date"])
    op.create_index("ix_student_attendance_sessions_tenant_status", "student_attendance_sessions", ["tenant_id", "status"])

    op.create_table(
        "attendance_policies",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=32), server_default="all", nullable=False),
        sa.Column("minimum_percentage", sa.Numeric(5, 2), server_default=sa.text("75.00"), nullable=False),
        sa.Column("late_after_minutes", sa.Integer(), nullable=True),
        sa.Column("absent_after_minutes", sa.Integer(), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_attendance_policies_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_policies")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_attendance_policies_tenant_code"),
    )
    op.create_index(op.f("ix_attendance_policies_tenant_id"), "attendance_policies", ["tenant_id"])
    op.create_index(op.f("ix_attendance_policies_deleted_at"), "attendance_policies", ["deleted_at"])
    op.create_index("ix_attendance_policies_tenant_default", "attendance_policies", ["tenant_id", "is_default"])
    op.create_index("ix_attendance_policies_tenant_scope", "attendance_policies", ["tenant_id", "scope"])

    op.create_table(
        "student_attendance_records",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="present", nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("marked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["student_attendance_sessions.id"], name=op.f("fk_student_attendance_records_session_id_student_attendance_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_attendance_records_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_student_attendance_records_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_attendance_records")),
        sa.UniqueConstraint("tenant_id", "session_id", "student_id", name="uq_student_attendance_records_session_student"),
    )
    op.create_index(op.f("ix_student_attendance_records_tenant_id"), "student_attendance_records", ["tenant_id"])
    op.create_index("ix_student_attendance_records_tenant_session", "student_attendance_records", ["tenant_id", "session_id"])
    op.create_index("ix_student_attendance_records_tenant_status", "student_attendance_records", ["tenant_id", "status"])
    op.create_index("ix_student_attendance_records_tenant_student", "student_attendance_records", ["tenant_id", "student_id"])

    op.create_table(
        "employee_attendance_records",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="present", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("marked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name=op.f("fk_employee_attendance_records_employee_id_employees"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_employee_attendance_records_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_attendance_records")),
        sa.UniqueConstraint("tenant_id", "employee_id", "date", name="uq_employee_attendance_records_employee_date"),
    )
    op.create_index(op.f("ix_employee_attendance_records_tenant_id"), "employee_attendance_records", ["tenant_id"])
    op.create_index("ix_employee_attendance_records_tenant_date", "employee_attendance_records", ["tenant_id", "date"])
    op.create_index("ix_employee_attendance_records_tenant_employee", "employee_attendance_records", ["tenant_id", "employee_id"])
    op.create_index("ix_employee_attendance_records_tenant_status", "employee_attendance_records", ["tenant_id", "status"])

    op.create_table(
        "attendance_correction_requests",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("student_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_record_id"], ["employee_attendance_records.id"], name=op.f("fk_attendance_correction_requests_employee_record_id_employee_attendance_records"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_record_id"], ["student_attendance_records.id"], name=op.f("fk_attendance_correction_requests_student_record_id_student_attendance_records"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_attendance_correction_requests_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_correction_requests")),
    )
    op.create_index(op.f("ix_attendance_correction_requests_tenant_id"), "attendance_correction_requests", ["tenant_id"])
    op.create_index("ix_attendance_correction_requests_tenant_requester", "attendance_correction_requests", ["tenant_id", "requester_user_id"])
    op.create_index("ix_attendance_correction_requests_tenant_status", "attendance_correction_requests", ["tenant_id", "status"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_attendance_correction_requests_tenant_status", table_name="attendance_correction_requests")
    op.drop_index("ix_attendance_correction_requests_tenant_requester", table_name="attendance_correction_requests")
    op.drop_index(op.f("ix_attendance_correction_requests_tenant_id"), table_name="attendance_correction_requests")
    op.drop_table("attendance_correction_requests")

    op.drop_index("ix_employee_attendance_records_tenant_status", table_name="employee_attendance_records")
    op.drop_index("ix_employee_attendance_records_tenant_employee", table_name="employee_attendance_records")
    op.drop_index("ix_employee_attendance_records_tenant_date", table_name="employee_attendance_records")
    op.drop_index(op.f("ix_employee_attendance_records_tenant_id"), table_name="employee_attendance_records")
    op.drop_table("employee_attendance_records")

    op.drop_index("ix_student_attendance_records_tenant_student", table_name="student_attendance_records")
    op.drop_index("ix_student_attendance_records_tenant_status", table_name="student_attendance_records")
    op.drop_index("ix_student_attendance_records_tenant_session", table_name="student_attendance_records")
    op.drop_index(op.f("ix_student_attendance_records_tenant_id"), table_name="student_attendance_records")
    op.drop_table("student_attendance_records")

    op.drop_index("ix_attendance_policies_tenant_scope", table_name="attendance_policies")
    op.drop_index("ix_attendance_policies_tenant_default", table_name="attendance_policies")
    op.drop_index(op.f("ix_attendance_policies_deleted_at"), table_name="attendance_policies")
    op.drop_index(op.f("ix_attendance_policies_tenant_id"), table_name="attendance_policies")
    op.drop_table("attendance_policies")

    op.drop_index("ix_student_attendance_sessions_tenant_status", table_name="student_attendance_sessions")
    op.drop_index("ix_student_attendance_sessions_tenant_date", table_name="student_attendance_sessions")
    op.drop_index("ix_student_attendance_sessions_tenant_batch", table_name="student_attendance_sessions")
    op.drop_index(op.f("ix_student_attendance_sessions_tenant_id"), table_name="student_attendance_sessions")
    op.drop_table("student_attendance_sessions")
