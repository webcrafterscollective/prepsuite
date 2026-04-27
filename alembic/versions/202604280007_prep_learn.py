"""prep learn

Revision ID: 202604280007
Revises: 202604280006
Create Date: 2026-04-28 07:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280007"
down_revision: str | None = "202604280006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "courses",
    "course_modules",
    "lessons",
    "lesson_resources",
    "course_batches",
    "course_teachers",
    "course_publish_history",
    "course_prerequisites",
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
        "courses",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("level", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("visibility", sa.String(length=32), server_default="private", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_courses_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_courses_tenant_slug"),
    )
    op.create_index(op.f("ix_courses_tenant_id"), "courses", ["tenant_id"])
    op.create_index(op.f("ix_courses_deleted_at"), "courses", ["deleted_at"])
    op.create_index("ix_courses_tenant_category", "courses", ["tenant_id", "category"])
    op.create_index("ix_courses_tenant_status", "courses", ["tenant_id", "status"])

    op.create_table(
        "course_modules",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_course_modules_course_id_courses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_course_modules_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_modules")),
        sa.UniqueConstraint("tenant_id", "course_id", "order_index", name="uq_modules_order"),
    )
    op.create_index(op.f("ix_course_modules_tenant_id"), "course_modules", ["tenant_id"])
    op.create_index(op.f("ix_course_modules_deleted_at"), "course_modules", ["deleted_at"])
    op.create_index("ix_course_modules_tenant_course", "course_modules", ["tenant_id", "course_id"])

    op.create_table(
        "lessons",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("lesson_type", sa.String(length=32), server_default="mixed", nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_preview", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("completion_rule", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["course_modules.id"], name=op.f("fk_lessons_module_id_course_modules"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_lessons_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lessons")),
        sa.UniqueConstraint("tenant_id", "module_id", "order_index", name="uq_lessons_order"),
    )
    op.create_index(op.f("ix_lessons_tenant_id"), "lessons", ["tenant_id"])
    op.create_index(op.f("ix_lessons_deleted_at"), "lessons", ["deleted_at"])
    op.create_index("ix_lessons_tenant_module", "lessons", ["tenant_id", "module_id"])

    op.create_table(
        "lesson_resources",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("content_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], name=op.f("fk_lesson_resources_lesson_id_lessons"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_lesson_resources_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_resources")),
    )
    op.create_index(op.f("ix_lesson_resources_tenant_id"), "lesson_resources", ["tenant_id"])
    op.create_index(op.f("ix_lesson_resources_deleted_at"), "lesson_resources", ["deleted_at"])
    op.create_index("ix_lesson_resources_tenant_lesson", "lesson_resources", ["tenant_id", "lesson_id"])

    op.create_table(
        "course_batches",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_course_batches_batch_id_batches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_course_batches_course_id_courses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_course_batches_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_batches")),
        sa.UniqueConstraint("tenant_id", "course_id", "batch_id", name="uq_course_batches_course_batch"),
    )
    op.create_index(op.f("ix_course_batches_tenant_id"), "course_batches", ["tenant_id"])
    op.create_index("ix_course_batches_tenant_course", "course_batches", ["tenant_id", "course_id"])

    op.create_table(
        "course_teachers",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_course_teachers_course_id_courses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["employees.id"], name=op.f("fk_course_teachers_teacher_id_employees"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_course_teachers_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_teachers")),
        sa.UniqueConstraint("tenant_id", "course_id", "teacher_id", name="uq_course_teachers_course_teacher"),
    )
    op.create_index(op.f("ix_course_teachers_tenant_id"), "course_teachers", ["tenant_id"])
    op.create_index("ix_course_teachers_tenant_course", "course_teachers", ["tenant_id", "course_id"])

    op.create_table(
        "course_publish_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_course_publish_history_course_id_courses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_course_publish_history_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_publish_history")),
    )
    op.create_index(op.f("ix_course_publish_history_tenant_id"), "course_publish_history", ["tenant_id"])
    op.create_index("ix_course_publish_history_tenant_course", "course_publish_history", ["tenant_id", "course_id"])

    op.create_table(
        "course_prerequisites",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prerequisite_course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_course_prerequisites_course_id_courses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prerequisite_course_id"], ["courses.id"], name=op.f("fk_course_prerequisites_prerequisite_course_id_courses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_course_prerequisites_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_prerequisites")),
        sa.UniqueConstraint("tenant_id", "course_id", "prerequisite_course_id", name="uq_course_prerequisites_pair"),
    )
    op.create_index(op.f("ix_course_prerequisites_tenant_id"), "course_prerequisites", ["tenant_id"])
    op.create_index("ix_course_prerequisites_tenant_course", "course_prerequisites", ["tenant_id", "course_id"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_course_prerequisites_tenant_course", table_name="course_prerequisites")
    op.drop_index(op.f("ix_course_prerequisites_tenant_id"), table_name="course_prerequisites")
    op.drop_table("course_prerequisites")

    op.drop_index("ix_course_publish_history_tenant_course", table_name="course_publish_history")
    op.drop_index(op.f("ix_course_publish_history_tenant_id"), table_name="course_publish_history")
    op.drop_table("course_publish_history")

    op.drop_index("ix_course_teachers_tenant_course", table_name="course_teachers")
    op.drop_index(op.f("ix_course_teachers_tenant_id"), table_name="course_teachers")
    op.drop_table("course_teachers")

    op.drop_index("ix_course_batches_tenant_course", table_name="course_batches")
    op.drop_index(op.f("ix_course_batches_tenant_id"), table_name="course_batches")
    op.drop_table("course_batches")

    op.drop_index("ix_lesson_resources_tenant_lesson", table_name="lesson_resources")
    op.drop_index(op.f("ix_lesson_resources_deleted_at"), table_name="lesson_resources")
    op.drop_index(op.f("ix_lesson_resources_tenant_id"), table_name="lesson_resources")
    op.drop_table("lesson_resources")

    op.drop_index("ix_lessons_tenant_module", table_name="lessons")
    op.drop_index(op.f("ix_lessons_deleted_at"), table_name="lessons")
    op.drop_index(op.f("ix_lessons_tenant_id"), table_name="lessons")
    op.drop_table("lessons")

    op.drop_index("ix_course_modules_tenant_course", table_name="course_modules")
    op.drop_index(op.f("ix_course_modules_deleted_at"), table_name="course_modules")
    op.drop_index(op.f("ix_course_modules_tenant_id"), table_name="course_modules")
    op.drop_table("course_modules")

    op.drop_index("ix_courses_tenant_status", table_name="courses")
    op.drop_index("ix_courses_tenant_category", table_name="courses")
    op.drop_index(op.f("ix_courses_deleted_at"), table_name="courses")
    op.drop_index(op.f("ix_courses_tenant_id"), table_name="courses")
    op.drop_table("courses")
