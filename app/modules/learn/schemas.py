from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.core.pagination import CursorPage
from app.modules.learn.enums import (
    CourseAssignmentStatus,
    CourseStatus,
    CourseVisibility,
    LessonResourceType,
    LessonType,
)
from app.shared.schemas import Schema

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


class CourseCreate(Schema):
    title: str = Field(min_length=1, max_length=240)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = None
    category: str | None = Field(default=None, max_length=120)
    level: str | None = Field(default=None, max_length=80)
    visibility: CourseVisibility = CourseVisibility.PRIVATE

    @model_validator(mode="after")
    def normalize_slug(self) -> CourseCreate:
        self.slug = slugify(self.slug or self.title)
        if not SLUG_PATTERN.match(self.slug):
            raise ValueError("slug must be URL-safe and between 3 and 120 characters")
        return self


class CourseUpdate(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = None
    category: str | None = Field(default=None, max_length=120)
    level: str | None = Field(default=None, max_length=80)
    visibility: CourseVisibility | None = None
    status: CourseStatus | None = None

    @field_validator("slug")
    @classmethod
    def normalize_slug_value(cls, value: str | None) -> str | None:
        if value is None:
            return value
        slug = slugify(value)
        if not SLUG_PATTERN.match(slug):
            raise ValueError("slug must be URL-safe and between 3 and 120 characters")
        return slug


class CourseRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    slug: str
    description: str | None
    category: str | None
    level: str | None
    status: CourseStatus
    visibility: CourseVisibility
    created_by: uuid.UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class CoursePage(CursorPage[CourseRead]):
    pass


class ModuleCreate(Schema):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    order_index: int | None = Field(default=None, ge=0)


class ModuleUpdate(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    order_index: int | None = Field(default=None, ge=0)


class LessonResourceCreate(Schema):
    title: str = Field(min_length=1, max_length=240)
    resource_type: LessonResourceType
    url: str | None = None
    storage_key: str | None = None
    content_asset_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    order_index: int | None = Field(default=None, ge=0)


class LessonResourceRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    resource_type: LessonResourceType
    url: str | None
    storage_key: str | None
    content_asset_id: uuid.UUID | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    order_index: int
    created_at: datetime
    updated_at: datetime


class LessonCreate(Schema):
    title: str = Field(min_length=1, max_length=240)
    lesson_type: LessonType = LessonType.MIXED
    content: dict[str, Any] = Field(default_factory=dict)
    duration_minutes: int | None = Field(default=None, ge=0)
    order_index: int | None = Field(default=None, ge=0)
    is_preview: bool = False
    completion_rule: dict[str, Any] = Field(default_factory=dict)
    resources: list[LessonResourceCreate] = Field(default_factory=list, max_length=25)


class LessonUpdate(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    lesson_type: LessonType | None = None
    content: dict[str, Any] | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    order_index: int | None = Field(default=None, ge=0)
    is_preview: bool | None = None
    completion_rule: dict[str, Any] | None = None


class LessonRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    module_id: uuid.UUID
    title: str
    lesson_type: LessonType
    content: dict[str, Any]
    duration_minutes: int | None
    order_index: int
    is_preview: bool
    completion_rule: dict[str, Any]
    resources: list[LessonResourceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ModuleRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    lessons: list[LessonRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class CourseBatchRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    batch_id: uuid.UUID
    status: CourseAssignmentStatus
    created_at: datetime
    updated_at: datetime


class CourseTeacherRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    teacher_id: uuid.UUID
    status: CourseAssignmentStatus
    created_at: datetime
    updated_at: datetime


class CoursePublishHistoryRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    published_by: uuid.UUID | None
    previous_status: CourseStatus | None
    new_status: CourseStatus
    published_at: datetime
    notes: str | None
    created_at: datetime


class CoursePrerequisiteRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    course_id: uuid.UUID
    prerequisite_course_id: uuid.UUID
    created_at: datetime


class CourseDetailRead(Schema):
    course: CourseRead
    modules: list[ModuleRead]
    batches: list[CourseBatchRead]
    teachers: list[CourseTeacherRead]
    publish_history: list[CoursePublishHistoryRead]
    prerequisites: list[CoursePrerequisiteRead]


class CourseOutlineRead(Schema):
    course: CourseRead
    modules: list[ModuleRead]


class CoursePublishRequest(Schema):
    notes: str | None = None


class ModuleReorderItem(Schema):
    module_id: uuid.UUID
    order_index: int = Field(ge=0)


class LessonReorderItem(Schema):
    lesson_id: uuid.UUID
    order_index: int = Field(ge=0)


class CourseReorderRequest(Schema):
    modules: list[ModuleReorderItem] = Field(default_factory=list)
    lessons: list[LessonReorderItem] = Field(default_factory=list)


class CourseAssignBatchRequest(Schema):
    batch_id: uuid.UUID


class CourseAssignTeacherRequest(Schema):
    teacher_id: uuid.UUID


class CoursePrerequisiteCreate(Schema):
    prerequisite_course_id: uuid.UUID
