from __future__ import annotations

from enum import StrEnum


class AssessmentType(StrEnum):
    EXAM = "exam"
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    PRACTICE = "practice"


class AssessmentStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    LIVE = "live"
    CLOSED = "closed"
    EVALUATED = "evaluated"
    PUBLISHED = "published"


class AttemptStatus(StrEnum):
    STARTED = "started"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"
    EVALUATED = "evaluated"


class AnswerEvaluationStatus(StrEnum):
    PENDING = "pending"
    AUTO_EVALUATED = "auto_evaluated"
    MANUAL_EVALUATED = "manual_evaluated"


class ResultStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class AssignmentSubmissionStatus(StrEnum):
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"
