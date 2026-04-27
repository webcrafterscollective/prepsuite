"""prep people

Revision ID: 202604280006
Revises: 202604280005
Create Date: 2026-04-28 06:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280006"
down_revision: str | None = "202604280005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "departments",
    "employees",
    "employee_profiles",
    "employee_documents",
    "teacher_assignments",
    "employee_status_history",
    "employee_notes",
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
        "departments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_departments_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )
    op.create_index(op.f("ix_departments_tenant_id"), "departments", ["tenant_id"])
    op.create_index(op.f("ix_departments_deleted_at"), "departments", ["deleted_at"])
    op.create_index("ix_departments_tenant_status", "departments", ["tenant_id", "status"])

    op.create_table(
        "employees",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_code", sa.String(length=80), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("employee_type", sa.String(length=40), server_default="teacher", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name=op.f("fk_employees_department_id_departments"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_employees_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_employees_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employees")),
        sa.UniqueConstraint("tenant_id", "employee_code", name="uq_employees_tenant_code"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_employees_tenant_user"),
    )
    op.create_index(op.f("ix_employees_tenant_id"), "employees", ["tenant_id"])
    op.create_index(op.f("ix_employees_user_id"), "employees", ["user_id"])
    op.create_index(op.f("ix_employees_department_id"), "employees", ["department_id"])
    op.create_index(op.f("ix_employees_deleted_at"), "employees", ["deleted_at"])
    op.create_index("ix_employees_tenant_name", "employees", ["tenant_id", "last_name", "first_name"])
    op.create_index("ix_employees_tenant_status", "employees", ["tenant_id", "status"])
    op.create_index("ix_employees_tenant_type", "employees", ["tenant_id", "employee_type"])

    op.create_table(
        "employee_profiles",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_title", sa.String(length=160), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("qualifications", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("emergency_contact", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name=op.f("fk_employee_profiles_employee_id_employees"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_employee_profiles_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_profiles")),
        sa.UniqueConstraint("employee_id", name="uq_employee_profiles_employee_id"),
    )
    op.create_index(op.f("ix_employee_profiles_tenant_id"), "employee_profiles", ["tenant_id"])
    op.create_index(op.f("ix_employee_profiles_employee_id"), "employee_profiles", ["employee_id"])

    op.create_table(
        "employee_documents",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("document_type", sa.String(length=80), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name=op.f("fk_employee_documents_employee_id_employees"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_employee_documents_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_documents")),
    )
    op.create_index(op.f("ix_employee_documents_tenant_id"), "employee_documents", ["tenant_id"])
    op.create_index(op.f("ix_employee_documents_deleted_at"), "employee_documents", ["deleted_at"])
    op.create_index("ix_employee_documents_tenant_employee", "employee_documents", ["tenant_id", "employee_id"])

    op.create_table(
        "teacher_assignments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assignment_type", sa.String(length=80), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_teacher_assignments_batch_id_batches"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["teacher_id"], ["employees.id"], name=op.f("fk_teacher_assignments_teacher_id_employees"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_teacher_assignments_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teacher_assignments")),
    )
    op.create_index(op.f("ix_teacher_assignments_tenant_id"), "teacher_assignments", ["tenant_id"])
    op.create_index("ix_teacher_assignments_tenant_status", "teacher_assignments", ["tenant_id", "status"])
    op.create_index("ix_teacher_assignments_tenant_teacher", "teacher_assignments", ["tenant_id", "teacher_id"])

    op.create_table(
        "employee_status_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name=op.f("fk_employee_status_history_employee_id_employees"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_employee_status_history_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_status_history")),
    )
    op.create_index(op.f("ix_employee_status_history_tenant_id"), "employee_status_history", ["tenant_id"])
    op.create_index("ix_employee_status_history_tenant_employee", "employee_status_history", ["tenant_id", "employee_id"])

    op.create_table(
        "employee_notes",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note_type", sa.String(length=80), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=32), server_default="internal", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], name=op.f("fk_employee_notes_employee_id_employees"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_employee_notes_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_notes")),
    )
    op.create_index(op.f("ix_employee_notes_tenant_id"), "employee_notes", ["tenant_id"])
    op.create_index("ix_employee_notes_tenant_employee", "employee_notes", ["tenant_id", "employee_id"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_employee_notes_tenant_employee", table_name="employee_notes")
    op.drop_index(op.f("ix_employee_notes_tenant_id"), table_name="employee_notes")
    op.drop_table("employee_notes")

    op.drop_index("ix_employee_status_history_tenant_employee", table_name="employee_status_history")
    op.drop_index(op.f("ix_employee_status_history_tenant_id"), table_name="employee_status_history")
    op.drop_table("employee_status_history")

    op.drop_index("ix_teacher_assignments_tenant_teacher", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_tenant_status", table_name="teacher_assignments")
    op.drop_index(op.f("ix_teacher_assignments_tenant_id"), table_name="teacher_assignments")
    op.drop_table("teacher_assignments")

    op.drop_index("ix_employee_documents_tenant_employee", table_name="employee_documents")
    op.drop_index(op.f("ix_employee_documents_deleted_at"), table_name="employee_documents")
    op.drop_index(op.f("ix_employee_documents_tenant_id"), table_name="employee_documents")
    op.drop_table("employee_documents")

    op.drop_index(op.f("ix_employee_profiles_employee_id"), table_name="employee_profiles")
    op.drop_index(op.f("ix_employee_profiles_tenant_id"), table_name="employee_profiles")
    op.drop_table("employee_profiles")

    op.drop_index("ix_employees_tenant_type", table_name="employees")
    op.drop_index("ix_employees_tenant_status", table_name="employees")
    op.drop_index("ix_employees_tenant_name", table_name="employees")
    op.drop_index(op.f("ix_employees_deleted_at"), table_name="employees")
    op.drop_index(op.f("ix_employees_department_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_user_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_tenant_id"), table_name="employees")
    op.drop_table("employees")

    op.drop_index("ix_departments_tenant_status", table_name="departments")
    op.drop_index(op.f("ix_departments_deleted_at"), table_name="departments")
    op.drop_index(op.f("ix_departments_tenant_id"), table_name="departments")
    op.drop_table("departments")
