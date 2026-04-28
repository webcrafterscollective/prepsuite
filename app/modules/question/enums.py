from __future__ import annotations

from enum import StrEnum


class QuestionType(StrEnum):
    MCQ = "mcq"
    MULTI_SELECT = "multi_select"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    CODING = "coding"
    FILL_BLANK = "fill_blank"
    MATCH_FOLLOWING = "match_following"


class QuestionDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class QuestionSetStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TopicStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AIGenerationJobStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    APPROVED = "approved"
    FAILED = "failed"
