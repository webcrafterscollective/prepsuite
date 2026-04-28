"""prep question

Revision ID: 202604280008
Revises: 202604280007
Create Date: 2026-04-28 08:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280008"
down_revision: str | None = "202604280007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "question_topics",
    "questions",
    "question_options",
    "question_tags",
    "question_sets",
    "question_set_items",
    "ai_question_generation_jobs",
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
        "question_topics",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["question_topics.id"], name=op.f("fk_question_topics_parent_id_question_topics"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_question_topics_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_topics")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_question_topics_tenant_slug"),
    )
    op.create_index(op.f("ix_question_topics_tenant_id"), "question_topics", ["tenant_id"])
    op.create_index("ix_question_topics_tenant_parent", "question_topics", ["tenant_id", "parent_id"])
    op.create_index("ix_question_topics_tenant_status", "question_topics", ["tenant_id", "status"])

    op.create_table(
        "questions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_type", sa.String(length=40), nullable=False),
        sa.Column("difficulty", sa.String(length=24), server_default="medium", nullable=False),
        sa.Column("bloom_level", sa.String(length=80), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("marks", sa.Numeric(10, 2), server_default=sa.text("1.00"), nullable=False),
        sa.Column("negative_marks", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_questions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["question_topics.id"], name=op.f("fk_questions_topic_id_question_topics"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
    )
    op.create_index(op.f("ix_questions_tenant_id"), "questions", ["tenant_id"])
    op.create_index(op.f("ix_questions_deleted_at"), "questions", ["deleted_at"])
    op.create_index("ix_questions_tenant_difficulty", "questions", ["tenant_id", "difficulty"])
    op.create_index("ix_questions_tenant_status", "questions", ["tenant_id", "status"])
    op.create_index("ix_questions_tenant_topic", "questions", ["tenant_id", "topic_id"])
    op.create_index("ix_questions_tenant_type", "questions", ["tenant_id", "question_type"])

    op.create_table(
        "question_options",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name=op.f("fk_question_options_question_id_questions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_question_options_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_options")),
        sa.UniqueConstraint("tenant_id", "question_id", "order_index", name="uq_question_options_order"),
    )
    op.create_index(op.f("ix_question_options_tenant_id"), "question_options", ["tenant_id"])
    op.create_index("ix_question_options_tenant_question", "question_options", ["tenant_id", "question_id"])

    op.create_table(
        "question_tags",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name=op.f("fk_question_tags_question_id_questions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_question_tags_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_tags")),
        sa.UniqueConstraint("tenant_id", "question_id", "name", name="uq_question_tags_name"),
    )
    op.create_index(op.f("ix_question_tags_tenant_id"), "question_tags", ["tenant_id"])
    op.create_index("ix_question_tags_tenant_name", "question_tags", ["tenant_id", "name"])

    op.create_table(
        "question_sets",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("total_marks", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("difficulty_distribution", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("topic_distribution", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_question_sets_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_sets")),
        sa.UniqueConstraint("tenant_id", "title", name="uq_question_sets_tenant_title"),
    )
    op.create_index(op.f("ix_question_sets_tenant_id"), "question_sets", ["tenant_id"])
    op.create_index(op.f("ix_question_sets_deleted_at"), "question_sets", ["deleted_at"])
    op.create_index("ix_question_sets_tenant_status", "question_sets", ["tenant_id", "status"])

    op.create_table(
        "question_set_items",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("marks_override", sa.Numeric(10, 2), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name=op.f("fk_question_set_items_question_id_questions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["question_set_id"], ["question_sets.id"], name=op.f("fk_question_set_items_question_set_id_question_sets"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_question_set_items_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_set_items")),
        sa.UniqueConstraint("tenant_id", "question_set_id", "question_id", name="uq_question_set_items_question"),
        sa.UniqueConstraint("tenant_id", "question_set_id", "order_index", name="uq_question_set_items_order"),
    )
    op.create_index(op.f("ix_question_set_items_tenant_id"), "question_set_items", ["tenant_id"])
    op.create_index("ix_question_set_items_tenant_set", "question_set_items", ["tenant_id", "question_set_id"])

    op.create_table(
        "ai_question_generation_jobs",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=180), nullable=False),
        sa.Column("difficulty", sa.String(length=24), nullable=False),
        sa.Column("question_type", sa.String(length=40), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_ai_question_generation_jobs_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_question_generation_jobs")),
    )
    op.create_index(op.f("ix_ai_question_generation_jobs_tenant_id"), "ai_question_generation_jobs", ["tenant_id"])
    op.create_index("ix_ai_generation_jobs_tenant_requested_by", "ai_question_generation_jobs", ["tenant_id", "requested_by"])
    op.create_index("ix_ai_generation_jobs_tenant_status", "ai_question_generation_jobs", ["tenant_id", "status"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_ai_generation_jobs_tenant_status", table_name="ai_question_generation_jobs")
    op.drop_index("ix_ai_generation_jobs_tenant_requested_by", table_name="ai_question_generation_jobs")
    op.drop_index(op.f("ix_ai_question_generation_jobs_tenant_id"), table_name="ai_question_generation_jobs")
    op.drop_table("ai_question_generation_jobs")

    op.drop_index("ix_question_set_items_tenant_set", table_name="question_set_items")
    op.drop_index(op.f("ix_question_set_items_tenant_id"), table_name="question_set_items")
    op.drop_table("question_set_items")

    op.drop_index("ix_question_sets_tenant_status", table_name="question_sets")
    op.drop_index(op.f("ix_question_sets_deleted_at"), table_name="question_sets")
    op.drop_index(op.f("ix_question_sets_tenant_id"), table_name="question_sets")
    op.drop_table("question_sets")

    op.drop_index("ix_question_tags_tenant_name", table_name="question_tags")
    op.drop_index(op.f("ix_question_tags_tenant_id"), table_name="question_tags")
    op.drop_table("question_tags")

    op.drop_index("ix_question_options_tenant_question", table_name="question_options")
    op.drop_index(op.f("ix_question_options_tenant_id"), table_name="question_options")
    op.drop_table("question_options")

    op.drop_index("ix_questions_tenant_type", table_name="questions")
    op.drop_index("ix_questions_tenant_topic", table_name="questions")
    op.drop_index("ix_questions_tenant_status", table_name="questions")
    op.drop_index("ix_questions_tenant_difficulty", table_name="questions")
    op.drop_index(op.f("ix_questions_deleted_at"), table_name="questions")
    op.drop_index(op.f("ix_questions_tenant_id"), table_name="questions")
    op.drop_table("questions")

    op.drop_index("ix_question_topics_tenant_status", table_name="question_topics")
    op.drop_index("ix_question_topics_tenant_parent", table_name="question_topics")
    op.drop_index(op.f("ix_question_topics_tenant_id"), table_name="question_topics")
    op.drop_table("question_topics")
