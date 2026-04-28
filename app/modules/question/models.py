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

from app.modules.question.enums import (
    AIGenerationJobStatus,
    QuestionDifficulty,
    QuestionSetStatus,
    QuestionStatus,
    TopicStatus,
)
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionTopic(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "question_topics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_question_topics_tenant_slug"),
        Index("ix_question_topics_tenant_parent", "tenant_id", "parent_id"),
        Index("ix_question_topics_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_topics.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TopicStatus.ACTIVE.value,
        server_default=TopicStatus.ACTIVE.value,
    )

    questions: Mapped[list[Question]] = relationship(back_populates="topic")


class Question(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_tenant_topic", "tenant_id", "topic_id"),
        Index("ix_questions_tenant_status", "tenant_id", "status"),
        Index("ix_questions_tenant_difficulty", "tenant_id", "difficulty"),
        Index("ix_questions_tenant_type", "tenant_id", "question_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_topics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    difficulty: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=QuestionDifficulty.MEDIUM.value,
        server_default=QuestionDifficulty.MEDIUM.value,
    )
    bloom_level: Mapped[str | None] = mapped_column(String(80))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    marks: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("1.00"),
        server_default=text("1.00"),
    )
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
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=QuestionStatus.DRAFT.value,
        server_default=QuestionStatus.DRAFT.value,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    topic: Mapped[QuestionTopic] = relationship(back_populates="questions")
    options: Mapped[list[QuestionOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list[QuestionTag]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
    set_items: Mapped[list[QuestionSetItem]] = relationship(back_populates="question")


class QuestionOption(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "question_id",
            "order_index",
            name="uq_question_options_order",
        ),
        Index("ix_question_options_tenant_question", "tenant_id", "question_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    explanation: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[Question] = relationship(back_populates="options")


class QuestionTag(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "question_tags"
    __table_args__ = (
        UniqueConstraint("tenant_id", "question_id", "name", name="uq_question_tags_name"),
        Index("ix_question_tags_tenant_name", "tenant_id", "name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    question: Mapped[Question] = relationship(back_populates="tags")


class QuestionSet(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "question_sets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "title", name="uq_question_sets_tenant_title"),
        Index("ix_question_sets_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    total_marks: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00"),
    )
    difficulty_distribution: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    topic_distribution: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=QuestionSetStatus.DRAFT.value,
        server_default=QuestionSetStatus.DRAFT.value,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    items: Mapped[list[QuestionSetItem]] = relationship(
        back_populates="question_set",
        cascade="all, delete-orphan",
    )


class QuestionSetItem(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "question_set_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "question_set_id",
            "question_id",
            name="uq_question_set_items_question",
        ),
        UniqueConstraint(
            "tenant_id",
            "question_set_id",
            "order_index",
            name="uq_question_set_items_order",
        ),
        Index("ix_question_set_items_tenant_set", "tenant_id", "question_set_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    marks_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    question_set: Mapped[QuestionSet] = relationship(back_populates="items")
    question: Mapped[Question] = relationship(back_populates="set_items")


class AIQuestionGenerationJob(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "ai_question_generation_jobs"
    __table_args__ = (
        Index("ix_ai_generation_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_ai_generation_jobs_tenant_requested_by", "tenant_id", "requested_by"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(180), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(24), nullable=False)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AIGenerationJobStatus.PENDING.value,
        server_default=AIGenerationJobStatus.PENDING.value,
    )
    output: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
