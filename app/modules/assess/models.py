from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.assess.enums import (
    AnswerEvaluationStatus,
    AssessmentStatus,
    AssignmentSubmissionStatus,
    AttemptStatus,
    ResultStatus,
)
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        Index("ix_assessments_tenant_status", "tenant_id", "status"),
        Index("ix_assessments_tenant_batch", "tenant_id", "batch_id"),
        Index("ix_assessments_tenant_course", "tenant_id", "course_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="SET NULL"),
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
    )
    question_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_sets.id", ondelete="SET NULL"),
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AssessmentStatus.DRAFT.value,
        server_default=AssessmentStatus.DRAFT.value,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    total_marks: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    sections: Mapped[list[AssessmentSection]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
    questions: Mapped[list[AssessmentQuestion]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
    attempts: Mapped[list[AssessmentAttempt]] = relationship(back_populates="assessment")
    results: Mapped[list[AssessmentResult]] = relationship(back_populates="assessment")


class AssessmentSection(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assessment_sections"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "order_index",
            name="uq_assessment_sections_order",
        ),
        Index("ix_assessment_sections_tenant_assessment", "tenant_id", "assessment_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    total_marks: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )

    assessment: Mapped[Assessment] = relationship(back_populates="sections")
    questions: Mapped[list[AssessmentQuestion]] = relationship(back_populates="section")


class AssessmentQuestion(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "order_index",
            name="uq_assessment_questions_order",
        ),
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "question_id",
            name="uq_assessment_questions_question",
        ),
        Index("ix_assessment_questions_tenant_assessment", "tenant_id", "assessment_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_sections.id", ondelete="SET NULL"),
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    marks: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    negative_marks: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    assessment: Mapped[Assessment] = relationship(back_populates="questions")
    section: Mapped[AssessmentSection | None] = relationship(back_populates="questions")
    answers: Mapped[list[AssessmentAnswer]] = relationship(back_populates="assessment_question")


class AssessmentAttempt(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "student_id",
            name="uq_assessment_attempts_student",
        ),
        Index("ix_assessment_attempts_tenant_assessment", "tenant_id", "assessment_id"),
        Index("ix_assessment_attempts_tenant_student", "tenant_id", "student_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AttemptStatus.STARTED.value,
        server_default=AttemptStatus.STARTED.value,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    assessment: Mapped[Assessment] = relationship(back_populates="attempts")
    answers: Mapped[list[AssessmentAnswer]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )
    results: Mapped[list[AssessmentResult]] = relationship(back_populates="attempt")


class AssessmentAnswer(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "attempt_id",
            "assessment_question_id",
            name="uq_assessment_answers_question",
        ),
        Index("ix_assessment_answers_tenant_attempt", "tenant_id", "attempt_id"),
        Index("ix_assessment_answers_tenant_question", "tenant_id", "assessment_question_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    answer: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AnswerEvaluationStatus.PENDING.value,
        server_default=AnswerEvaluationStatus.PENDING.value,
    )
    is_correct: Mapped[bool | None] = mapped_column()
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    evaluated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(160))

    attempt: Mapped[AssessmentAttempt] = relationship(back_populates="answers")
    assessment_question: Mapped[AssessmentQuestion] = relationship(back_populates="answers")
    comments: Mapped[list[EvaluationComment]] = relationship(
        back_populates="answer",
        cascade="all, delete-orphan",
    )


class AssessmentEvaluation(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assessment_evaluations"
    __table_args__ = (Index("ix_assessment_evaluations_tenant_attempt", "tenant_id", "attempt_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    comments: Mapped[list[EvaluationComment]] = relationship(back_populates="evaluation")


class AssessmentResult(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assessment_results"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "student_id",
            name="uq_assessment_results_student",
        ),
        Index("ix_assessment_results_tenant_assessment", "tenant_id", "assessment_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ResultStatus.DRAFT.value,
        server_default=ResultStatus.DRAFT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assessment: Mapped[Assessment] = relationship(back_populates="results")
    attempt: Mapped[AssessmentAttempt] = relationship(back_populates="results")


class AssignmentSubmission(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "student_id",
            name="uq_assignment_submissions_student",
        ),
        Index("ix_assignment_submissions_tenant_assessment", "tenant_id", "assessment_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="SET NULL"),
    )
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    storage_key: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AssignmentSubmissionStatus.SUBMITTED.value,
        server_default=AssignmentSubmissionStatus.SUBMITTED.value,
    )


class EvaluationComment(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "evaluation_comments"
    __table_args__ = (Index("ix_evaluation_comments_tenant_answer", "tenant_id", "answer_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_answers.id", ondelete="CASCADE"),
    )
    evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_evaluations.id", ondelete="CASCADE"),
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")

    answer: Mapped[AssessmentAnswer | None] = relationship(back_populates="comments")
    evaluation: Mapped[AssessmentEvaluation | None] = relationship(back_populates="comments")
