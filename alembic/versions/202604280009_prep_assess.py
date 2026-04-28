"""prep assess

Revision ID: 202604280009
Revises: 202604280008
Create Date: 2026-04-28 09:00:00.000000
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202604280009"
down_revision: str | None = "202604280008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_POLICY_EXPRESSION = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

RLS_TABLES = (
    "assessments",
    "assessment_sections",
    "assessment_questions",
    "assessment_attempts",
    "assessment_answers",
    "assessment_evaluations",
    "assessment_results",
    "assignment_submissions",
    "evaluation_comments",
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
        "assessments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("total_marks", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_assessments_batch_id_batches"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_assessments_course_id_courses"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_set_id"], ["question_sets.id"], name=op.f("fk_assessments_question_set_id_question_sets"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assessments_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessments")),
    )
    op.create_index(op.f("ix_assessments_tenant_id"), "assessments", ["tenant_id"])
    op.create_index(op.f("ix_assessments_deleted_at"), "assessments", ["deleted_at"])
    op.create_index("ix_assessments_tenant_batch", "assessments", ["tenant_id", "batch_id"])
    op.create_index("ix_assessments_tenant_course", "assessments", ["tenant_id", "course_id"])
    op.create_index("ix_assessments_tenant_status", "assessments", ["tenant_id", "status"])

    op.create_table(
        "assessment_sections",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("total_marks", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], name=op.f("fk_assessment_sections_assessment_id_assessments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assessment_sections_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_sections")),
        sa.UniqueConstraint("tenant_id", "assessment_id", "order_index", name="uq_assessment_sections_order"),
    )
    op.create_index(op.f("ix_assessment_sections_tenant_id"), "assessment_sections", ["tenant_id"])
    op.create_index("ix_assessment_sections_tenant_assessment", "assessment_sections", ["tenant_id", "assessment_id"])

    op.create_table(
        "assessment_questions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("marks", sa.Numeric(10, 2), nullable=False),
        sa.Column("negative_marks", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], name=op.f("fk_assessment_questions_assessment_id_assessments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name=op.f("fk_assessment_questions_question_id_questions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["section_id"], ["assessment_sections.id"], name=op.f("fk_assessment_questions_section_id_assessment_sections"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assessment_questions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_questions")),
        sa.UniqueConstraint("tenant_id", "assessment_id", "order_index", name="uq_assessment_questions_order"),
        sa.UniqueConstraint("tenant_id", "assessment_id", "question_id", name="uq_assessment_questions_question"),
    )
    op.create_index(op.f("ix_assessment_questions_tenant_id"), "assessment_questions", ["tenant_id"])
    op.create_index("ix_assessment_questions_tenant_assessment", "assessment_questions", ["tenant_id", "assessment_id"])

    op.create_table(
        "assessment_attempts",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="started", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Numeric(10, 2), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], name=op.f("fk_assessment_attempts_assessment_id_assessments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_assessment_attempts_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assessment_attempts_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_attempts")),
        sa.UniqueConstraint("tenant_id", "assessment_id", "student_id", name="uq_assessment_attempts_student"),
    )
    op.create_index(op.f("ix_assessment_attempts_tenant_id"), "assessment_attempts", ["tenant_id"])
    op.create_index("ix_assessment_attempts_tenant_assessment", "assessment_attempts", ["tenant_id", "assessment_id"])
    op.create_index("ix_assessment_attempts_tenant_student", "assessment_attempts", ["tenant_id", "student_id"])

    op.create_table(
        "assessment_answers",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Numeric(10, 2), nullable=True),
        sa.Column("evaluated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_question_id"], ["assessment_questions.id"], name=op.f("fk_assessment_answers_assessment_question_id_assessment_questions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], name=op.f("fk_assessment_answers_attempt_id_assessment_attempts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], name=op.f("fk_assessment_answers_question_id_questions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assessment_answers_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_answers")),
        sa.UniqueConstraint("tenant_id", "attempt_id", "assessment_question_id", name="uq_assessment_answers_question"),
    )
    op.create_index(op.f("ix_assessment_answers_tenant_id"), "assessment_answers", ["tenant_id"])
    op.create_index("ix_assessment_answers_tenant_attempt", "assessment_answers", ["tenant_id", "attempt_id"])
    op.create_index("ix_assessment_answers_tenant_question", "assessment_answers", ["tenant_id", "assessment_question_id"])

    op.create_table(
        "assessment_evaluations",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], name=op.f("fk_assessment_evaluations_attempt_id_assessment_attempts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assessment_evaluations_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_evaluations")),
    )
    op.create_index(op.f("ix_assessment_evaluations_tenant_id"), "assessment_evaluations", ["tenant_id"])
    op.create_index("ix_assessment_evaluations_tenant_attempt", "assessment_evaluations", ["tenant_id", "attempt_id"])

    op.create_table(
        "assessment_results",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Numeric(10, 2), nullable=False),
        sa.Column("percentage", sa.Numeric(6, 2), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], name=op.f("fk_assessment_results_assessment_id_assessments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], name=op.f("fk_assessment_results_attempt_id_assessment_attempts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_assessment_results_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assessment_results_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_results")),
        sa.UniqueConstraint("tenant_id", "assessment_id", "student_id", name="uq_assessment_results_student"),
    )
    op.create_index(op.f("ix_assessment_results_tenant_id"), "assessment_results", ["tenant_id"])
    op.create_index("ix_assessment_results_tenant_assessment", "assessment_results", ["tenant_id", "assessment_id"])

    op.create_table(
        "assignment_submissions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="submitted", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], name=op.f("fk_assignment_submissions_assessment_id_assessments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], name=op.f("fk_assignment_submissions_attempt_id_assessment_attempts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_assignment_submissions_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_assignment_submissions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment_submissions")),
        sa.UniqueConstraint("tenant_id", "assessment_id", "student_id", name="uq_assignment_submissions_student"),
    )
    op.create_index(op.f("ix_assignment_submissions_tenant_id"), "assignment_submissions", ["tenant_id"])
    op.create_index("ix_assignment_submissions_tenant_assessment", "assignment_submissions", ["tenant_id", "assessment_id"])

    op.create_table(
        "evaluation_comments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["assessment_answers.id"], name=op.f("fk_evaluation_comments_answer_id_assessment_answers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["assessment_evaluations.id"], name=op.f("fk_evaluation_comments_evaluation_id_assessment_evaluations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_evaluation_comments_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_comments")),
    )
    op.create_index(op.f("ix_evaluation_comments_tenant_id"), "evaluation_comments", ["tenant_id"])
    op.create_index("ix_evaluation_comments_tenant_answer", "evaluation_comments", ["tenant_id", "answer_id"])

    for table_name in RLS_TABLES:
        enable_rls(table_name)
    grant_app_role()


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        disable_rls(table_name)

    op.drop_index("ix_evaluation_comments_tenant_answer", table_name="evaluation_comments")
    op.drop_index(op.f("ix_evaluation_comments_tenant_id"), table_name="evaluation_comments")
    op.drop_table("evaluation_comments")

    op.drop_index("ix_assignment_submissions_tenant_assessment", table_name="assignment_submissions")
    op.drop_index(op.f("ix_assignment_submissions_tenant_id"), table_name="assignment_submissions")
    op.drop_table("assignment_submissions")

    op.drop_index("ix_assessment_results_tenant_assessment", table_name="assessment_results")
    op.drop_index(op.f("ix_assessment_results_tenant_id"), table_name="assessment_results")
    op.drop_table("assessment_results")

    op.drop_index("ix_assessment_evaluations_tenant_attempt", table_name="assessment_evaluations")
    op.drop_index(op.f("ix_assessment_evaluations_tenant_id"), table_name="assessment_evaluations")
    op.drop_table("assessment_evaluations")

    op.drop_index("ix_assessment_answers_tenant_question", table_name="assessment_answers")
    op.drop_index("ix_assessment_answers_tenant_attempt", table_name="assessment_answers")
    op.drop_index(op.f("ix_assessment_answers_tenant_id"), table_name="assessment_answers")
    op.drop_table("assessment_answers")

    op.drop_index("ix_assessment_attempts_tenant_student", table_name="assessment_attempts")
    op.drop_index("ix_assessment_attempts_tenant_assessment", table_name="assessment_attempts")
    op.drop_index(op.f("ix_assessment_attempts_tenant_id"), table_name="assessment_attempts")
    op.drop_table("assessment_attempts")

    op.drop_index("ix_assessment_questions_tenant_assessment", table_name="assessment_questions")
    op.drop_index(op.f("ix_assessment_questions_tenant_id"), table_name="assessment_questions")
    op.drop_table("assessment_questions")

    op.drop_index("ix_assessment_sections_tenant_assessment", table_name="assessment_sections")
    op.drop_index(op.f("ix_assessment_sections_tenant_id"), table_name="assessment_sections")
    op.drop_table("assessment_sections")

    op.drop_index("ix_assessments_tenant_status", table_name="assessments")
    op.drop_index("ix_assessments_tenant_course", table_name="assessments")
    op.drop_index("ix_assessments_tenant_batch", table_name="assessments")
    op.drop_index(op.f("ix_assessments_deleted_at"), table_name="assessments")
    op.drop_index(op.f("ix_assessments_tenant_id"), table_name="assessments")
    op.drop_table("assessments")
