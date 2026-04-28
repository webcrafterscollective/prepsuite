from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.core.pagination import CursorPage
from app.modules.question.enums import (
    AIGenerationJobStatus,
    QuestionDifficulty,
    QuestionSetStatus,
    QuestionStatus,
    QuestionType,
    TopicStatus,
)
from app.shared.schemas import Schema

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,138}[a-z0-9]$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        candidate = tag.strip().lower()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


class QuestionTopicCreate(Schema):
    name: str = Field(min_length=1, max_length=180)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = None
    parent_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def normalize_slug(self) -> QuestionTopicCreate:
        self.slug = slugify(self.slug or self.name)
        if not SLUG_PATTERN.match(self.slug):
            raise ValueError("slug must be URL-safe and between 3 and 140 characters")
        return self


class QuestionTopicRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    status: TopicStatus
    created_at: datetime
    updated_at: datetime


class QuestionOptionCreate(Schema):
    label: str | None = Field(default=None, max_length=20)
    body: str = Field(min_length=1)
    is_correct: bool = False
    explanation: str | None = None
    order_index: int | None = Field(default=None, ge=0)


class QuestionOptionRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    question_id: uuid.UUID
    label: str | None
    body: str
    is_correct: bool
    explanation: str | None
    order_index: int
    created_at: datetime
    updated_at: datetime


class QuestionCreate(Schema):
    topic_id: uuid.UUID
    question_type: QuestionType
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    bloom_level: str | None = Field(default=None, max_length=80)
    body: str = Field(min_length=1)
    explanation: str | None = None
    marks: Decimal = Field(default=Decimal("1.00"), gt=Decimal("0"))
    negative_marks: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: QuestionStatus = QuestionStatus.DRAFT
    options: list[QuestionOptionCreate] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("tags")
    @classmethod
    def normalize_question_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class QuestionUpdate(Schema):
    topic_id: uuid.UUID | None = None
    question_type: QuestionType | None = None
    difficulty: QuestionDifficulty | None = None
    bloom_level: str | None = Field(default=None, max_length=80)
    body: str | None = Field(default=None, min_length=1)
    explanation: str | None = None
    marks: Decimal | None = Field(default=None, gt=Decimal("0"))
    negative_marks: Decimal | None = Field(default=None, ge=Decimal("0"))
    metadata: dict[str, Any] | None = None
    status: QuestionStatus | None = None
    options: list[QuestionOptionCreate] | None = Field(default=None, max_length=20)
    tags: list[str] | None = Field(default=None, max_length=25)

    @field_validator("tags")
    @classmethod
    def normalize_question_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_tags(value)


class QuestionRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    topic_id: uuid.UUID
    question_type: QuestionType
    difficulty: QuestionDifficulty
    bloom_level: str | None
    body: str
    explanation: str | None
    marks: Decimal
    negative_marks: Decimal
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    status: QuestionStatus
    created_by: uuid.UUID | None
    options: list[QuestionOptionRead] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class QuestionPage(CursorPage[QuestionRead]):
    pass


class QuestionSetCreate(Schema):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    status: QuestionSetStatus = QuestionSetStatus.DRAFT


class QuestionSetRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    description: str | None
    total_marks: Decimal
    difficulty_distribution: dict[str, Any]
    topic_distribution: dict[str, Any]
    status: QuestionSetStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class QuestionSetPage(CursorPage[QuestionSetRead]):
    pass


class QuestionSetItemCreate(Schema):
    question_id: uuid.UUID
    order_index: int | None = Field(default=None, ge=0)
    marks_override: Decimal | None = Field(default=None, gt=Decimal("0"))


class QuestionSetItemRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    question_set_id: uuid.UUID
    question_id: uuid.UUID
    order_index: int
    marks_override: Decimal | None
    question: QuestionRead
    created_at: datetime
    updated_at: datetime


class QuestionSetDetailRead(Schema):
    question_set: QuestionSetRead
    items: list[QuestionSetItemRead]


class QuestionSetReorderItem(Schema):
    item_id: uuid.UUID
    order_index: int = Field(ge=0)


class QuestionSetReorderRequest(Schema):
    items: list[QuestionSetReorderItem] = Field(min_length=1)


class AIQuestionGenerationJobCreate(Schema):
    prompt: str = Field(min_length=1)
    topic: str = Field(min_length=1, max_length=180)
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    question_type: QuestionType = QuestionType.MCQ
    count: int = Field(default=5, ge=1, le=50)


class AIQuestionGenerationJobRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    requested_by: uuid.UUID | None
    prompt: str
    topic: str
    difficulty: QuestionDifficulty
    question_type: QuestionType
    count: int
    status: AIGenerationJobStatus
    output: dict[str, Any]
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AIQuestionGenerationApproveRequest(Schema):
    topic_id: uuid.UUID | None = None
    selected_indexes: list[int] | None = None
    status: QuestionStatus = QuestionStatus.REVIEWED


class AIQuestionGenerationApprovalRead(Schema):
    job: AIQuestionGenerationJobRead
    questions: list[QuestionRead]
