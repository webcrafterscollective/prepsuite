from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from app.core.pagination import CursorPage
from app.modules.assess.enums import (
    AnswerEvaluationStatus,
    AssessmentStatus,
    AssessmentType,
    AttemptStatus,
    ResultStatus,
)
from app.modules.question.schemas import QuestionRead
from app.shared.schemas import Schema


class AssessmentCreate(Schema):
    title: str = Field(min_length=1, max_length=240)
    type: AssessmentType = AssessmentType.QUIZ
    course_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    question_set_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1)
    settings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schedule_window(self) -> AssessmentCreate:
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be after starts_at")
        return self


class AssessmentUpdate(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    course_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1)
    settings: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_schedule_window(self) -> AssessmentUpdate:
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be after starts_at")
        return self


class AssessmentScheduleRequest(Schema):
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_window(self) -> AssessmentScheduleRequest:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class AssessmentPublishRequest(Schema):
    force: bool = False


class AssessmentSectionRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    assessment_id: uuid.UUID
    title: str
    instructions: str | None
    order_index: int
    total_marks: Decimal
    created_at: datetime
    updated_at: datetime


class AssessmentQuestionRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    assessment_id: uuid.UUID
    section_id: uuid.UUID | None
    question_id: uuid.UUID
    order_index: int
    marks: Decimal
    negative_marks: Decimal
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    question: QuestionRead | None = None
    created_at: datetime
    updated_at: datetime


class AssessmentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    course_id: uuid.UUID | None
    batch_id: uuid.UUID | None
    question_set_id: uuid.UUID | None
    title: str
    type: AssessmentType
    status: AssessmentStatus
    starts_at: datetime | None
    ends_at: datetime | None
    duration_minutes: int | None
    total_marks: Decimal
    settings: dict[str, Any]
    created_by: uuid.UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class AssessmentDetailRead(Schema):
    assessment: AssessmentRead
    sections: list[AssessmentSectionRead]
    questions: list[AssessmentQuestionRead]


class AssessmentPage(CursorPage[AssessmentRead]):
    pass


class AttemptStartRequest(Schema):
    student_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, max_length=160)


class AttemptRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    score: Decimal | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class AnswerSubmitRequest(Schema):
    assessment_question_id: uuid.UUID
    answer: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=160)


class AnswerRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    attempt_id: uuid.UUID
    assessment_question_id: uuid.UUID
    question_id: uuid.UUID
    answer: dict[str, Any]
    status: AnswerEvaluationStatus
    is_correct: bool | None
    score: Decimal | None
    evaluated_by: uuid.UUID | None
    evaluated_at: datetime | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


class AttemptSubmitRequest(Schema):
    idempotency_key: str | None = Field(default=None, max_length=160)
    auto_submit: bool = False


class ManualEvaluateAnswerRequest(Schema):
    score: Decimal = Field(ge=Decimal("0"))
    comment: str | None = None


class EvaluationQueueItemRead(Schema):
    answer: AnswerRead
    assessment_question: AssessmentQuestionRead
    attempt: AttemptRead


class ResultRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    attempt_id: uuid.UUID
    score: Decimal
    percentage: Decimal
    status: ResultStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResultsPublishRead(Schema):
    assessment: AssessmentRead
    results: list[ResultRead]


class AssessmentAnalyticsRead(Schema):
    assessment_id: uuid.UUID
    total_marks: Decimal
    attempts_started: int
    attempts_submitted: int
    attempts_evaluated: int
    results_published: int
    average_score: Decimal | None
    highest_score: Decimal | None
    lowest_score: Decimal | None
