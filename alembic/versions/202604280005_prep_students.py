"""prep students

Revision ID: 202604280005
Revises: 202604280004
Create Date: 2026-04-28 05:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280005"
down_revision: str | None = "202604280004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "students",
    "guardians",
    "student_guardians",
    "batches",
    "batch_students",
    "student_enrollments",
    "student_notes",
    "student_documents",
    "student_status_history",
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
        "students",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admission_no", sa.String(length=80), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_students_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
        sa.UniqueConstraint("tenant_id", "admission_no", name="uq_students_tenant_admission_no"),
    )
    op.create_index(op.f("ix_students_tenant_id"), "students", ["tenant_id"])
    op.create_index(op.f("ix_students_deleted_at"), "students", ["deleted_at"])
    op.create_index("ix_students_tenant_name", "students", ["tenant_id", "last_name", "first_name"])
    op.create_index("ix_students_tenant_status", "students", ["tenant_id", "status"])

    op.create_table(
        "guardians",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("relationship_type", sa.String(length=80), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_guardians_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guardians")),
    )
    op.create_index(op.f("ix_guardians_tenant_id"), "guardians", ["tenant_id"])
    op.create_index(op.f("ix_guardians_deleted_at"), "guardians", ["deleted_at"])
    op.create_index("ix_guardians_tenant_email", "guardians", ["tenant_id", "email"])
    op.create_index("ix_guardians_tenant_phone", "guardians", ["tenant_id", "phone"])

    op.create_table(
        "batches",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_batches_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batches")),
        sa.UniqueConstraint("tenant_id", "code", name="uq_batches_tenant_code"),
    )
    op.create_index(op.f("ix_batches_tenant_id"), "batches", ["tenant_id"])
    op.create_index(op.f("ix_batches_deleted_at"), "batches", ["deleted_at"])
    op.create_index("ix_batches_tenant_status", "batches", ["tenant_id", "status"])

    op.create_table(
        "student_guardians",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=80), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("can_pickup", sa.Boolean(), nullable=False),
        sa.Column("emergency_contact", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["guardian_id"], ["guardians.id"], name=op.f("fk_student_guardians_guardian_id_guardians"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_guardians_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_student_guardians_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_guardians")),
        sa.UniqueConstraint("tenant_id", "student_id", "guardian_id", name="uq_student_guardians_tenant_student_guardian"),
    )
    op.create_index(op.f("ix_student_guardians_tenant_id"), "student_guardians", ["tenant_id"])
    op.create_index("ix_student_guardians_tenant_primary", "student_guardians", ["tenant_id", "student_id", "is_primary"])

    op.create_table(
        "batch_students",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_batch_students_batch_id_batches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_batch_students_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_batch_students_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batch_students")),
        sa.UniqueConstraint("tenant_id", "batch_id", "student_id", name="uq_batch_students_membership"),
    )
    op.create_index(op.f("ix_batch_students_tenant_id"), "batch_students", ["tenant_id"])
    op.create_index("ix_batch_students_tenant_status", "batch_students", ["tenant_id", "batch_id", "status"])

    op.create_table(
        "student_enrollments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_student_enrollments_batch_id_batches"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_enrollments_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_student_enrollments_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_enrollments")),
    )
    op.create_index(op.f("ix_student_enrollments_tenant_id"), "student_enrollments", ["tenant_id"])
    op.create_index("ix_student_enrollments_tenant_course", "student_enrollments", ["tenant_id", "course_id"])
    op.create_index("ix_student_enrollments_tenant_student", "student_enrollments", ["tenant_id", "student_id"])

    op.create_table(
        "student_notes",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note_type", sa.String(length=80), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=32), server_default="internal", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_notes_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_student_notes_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_notes")),
    )
    op.create_index(op.f("ix_student_notes_tenant_id"), "student_notes", ["tenant_id"])
    op.create_index("ix_student_notes_tenant_student", "student_notes", ["tenant_id", "student_id"])

    op.create_table(
        "student_documents",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_documents_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_student_documents_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_documents")),
    )
    op.create_index(op.f("ix_student_documents_tenant_id"), "student_documents", ["tenant_id"])
    op.create_index(op.f("ix_student_documents_deleted_at"), "student_documents", ["deleted_at"])
    op.create_index("ix_student_documents_tenant_student", "student_documents", ["tenant_id", "student_id"])

    op.create_table(
        "student_status_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_status_history_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_student_status_history_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_status_history")),
    )
    op.create_index(op.f("ix_student_status_history_tenant_id"), "student_status_history", ["tenant_id"])
    op.create_index("ix_student_status_history_tenant_student", "student_status_history", ["tenant_id", "student_id"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_student_status_history_tenant_student", table_name="student_status_history")
    op.drop_index(op.f("ix_student_status_history_tenant_id"), table_name="student_status_history")
    op.drop_table("student_status_history")

    op.drop_index("ix_student_documents_tenant_student", table_name="student_documents")
    op.drop_index(op.f("ix_student_documents_deleted_at"), table_name="student_documents")
    op.drop_index(op.f("ix_student_documents_tenant_id"), table_name="student_documents")
    op.drop_table("student_documents")

    op.drop_index("ix_student_notes_tenant_student", table_name="student_notes")
    op.drop_index(op.f("ix_student_notes_tenant_id"), table_name="student_notes")
    op.drop_table("student_notes")

    op.drop_index("ix_student_enrollments_tenant_student", table_name="student_enrollments")
    op.drop_index("ix_student_enrollments_tenant_course", table_name="student_enrollments")
    op.drop_index(op.f("ix_student_enrollments_tenant_id"), table_name="student_enrollments")
    op.drop_table("student_enrollments")

    op.drop_index("ix_batch_students_tenant_status", table_name="batch_students")
    op.drop_index(op.f("ix_batch_students_tenant_id"), table_name="batch_students")
    op.drop_table("batch_students")

    op.drop_index("ix_student_guardians_tenant_primary", table_name="student_guardians")
    op.drop_index(op.f("ix_student_guardians_tenant_id"), table_name="student_guardians")
    op.drop_table("student_guardians")

    op.drop_index("ix_batches_tenant_status", table_name="batches")
    op.drop_index(op.f("ix_batches_deleted_at"), table_name="batches")
    op.drop_index(op.f("ix_batches_tenant_id"), table_name="batches")
    op.drop_table("batches")

    op.drop_index("ix_guardians_tenant_phone", table_name="guardians")
    op.drop_index("ix_guardians_tenant_email", table_name="guardians")
    op.drop_index(op.f("ix_guardians_deleted_at"), table_name="guardians")
    op.drop_index(op.f("ix_guardians_tenant_id"), table_name="guardians")
    op.drop_table("guardians")

    op.drop_index("ix_students_tenant_status", table_name="students")
    op.drop_index("ix_students_tenant_name", table_name="students")
    op.drop_index(op.f("ix_students_deleted_at"), table_name="students")
    op.drop_index(op.f("ix_students_tenant_id"), table_name="students")
    op.drop_table("students")
