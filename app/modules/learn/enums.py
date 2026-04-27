from __future__ import annotations

from enum import StrEnum


class CourseStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CourseVisibility(StrEnum):
    PRIVATE = "private"
    TENANT = "tenant"
    STUDENTS = "students"


class LessonType(StrEnum):
    VIDEO = "video"
    DOCUMENT = "document"
    LIVE = "live"
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    MIXED = "mixed"


class LessonResourceType(StrEnum):
    VIDEO = "video"
    DOCUMENT = "document"
    LINK = "link"
    DOWNLOAD = "download"
    EMBED = "embed"


class CourseAssignmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
