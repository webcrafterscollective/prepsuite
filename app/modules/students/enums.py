from __future__ import annotations

from enum import StrEnum


class StudentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    GRADUATED = "graduated"
    SUSPENDED = "suspended"
    DROPPED = "dropped"


class Gender(StrEnum):
    FEMALE = "female"
    MALE = "male"
    NON_BINARY = "non_binary"
    OTHER = "other"
    UNDISCLOSED = "undisclosed"


class BatchStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class BatchStudentStatus(StrEnum):
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    REMOVED = "removed"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StudentNoteVisibility(StrEnum):
    INTERNAL = "internal"
    TEACHERS = "teachers"
    GUARDIANS = "guardians"
