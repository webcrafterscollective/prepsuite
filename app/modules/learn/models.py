from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.learn.enums import (
    CourseAssignmentStatus,
    CourseStatus,
    CourseVisibility,
    LessonType,
)
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Course(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_courses_tenant_slug"),
        Index("ix_courses_tenant_status", "tenant_id", "status"),
        Index("ix_courses_tenant_category", "tenant_id", "category"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    level: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CourseStatus.DRAFT.value,
        server_default=CourseStatus.DRAFT.value,
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CourseVisibility.PRIVATE.value,
        server_default=CourseVisibility.PRIVATE.value,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    modules: Mapped[list[CourseModule]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    batches: Mapped[list[CourseBatch]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    teachers: Mapped[list[CourseTeacher]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    publish_history: Mapped[list[CoursePublishHistory]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    prerequisites: Mapped[list[CoursePrerequisite]] = relationship(
        foreign_keys="CoursePrerequisite.course_id",
        back_populates="course",
        cascade="all, delete-orphan",
    )


class CourseModule(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "course_modules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "course_id", "order_index", name="uq_modules_order"),
        Index("ix_course_modules_tenant_course", "tenant_id", "course_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
    )


class Lesson(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_id", "order_index", name="uq_lessons_order"),
        Index("ix_lessons_tenant_module", "tenant_id", "module_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_modules.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    lesson_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LessonType.MIXED.value,
        server_default=LessonType.MIXED.value,
    )
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_preview: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    completion_rule: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    module: Mapped[CourseModule] = relationship(back_populates="lessons")
    resources: Mapped[list[LessonResource]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
    )


class LessonResource(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "lesson_resources"
    __table_args__ = (Index("ix_lesson_resources_tenant_lesson", "tenant_id", "lesson_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    content_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    lesson: Mapped[Lesson] = relationship(back_populates="resources")


class CourseBatch(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "course_batches"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "course_id",
            "batch_id",
            name="uq_course_batches_course_batch",
        ),
        Index("ix_course_batches_tenant_course", "tenant_id", "course_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CourseAssignmentStatus.ACTIVE.value,
        server_default=CourseAssignmentStatus.ACTIVE.value,
    )

    course: Mapped[Course] = relationship(back_populates="batches")


class CourseTeacher(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "course_teachers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "course_id",
            "teacher_id",
            name="uq_course_teachers_course_teacher",
        ),
        Index("ix_course_teachers_tenant_course", "tenant_id", "course_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CourseAssignmentStatus.ACTIVE.value,
        server_default=CourseAssignmentStatus.ACTIVE.value,
    )

    course: Mapped[Course] = relationship(back_populates="teachers")


class CoursePublishHistory(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "course_publish_history"
    __table_args__ = (Index("ix_course_publish_history_tenant_course", "tenant_id", "course_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    notes: Mapped[str | None] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="publish_history")


class CoursePrerequisite(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "course_prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "course_id",
            "prerequisite_course_id",
            name="uq_course_prerequisites_pair",
        ),
        Index("ix_course_prerequisites_tenant_course", "tenant_id", "course_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    prerequisite_course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )

    course: Mapped[Course] = relationship(
        foreign_keys=[course_id],
        back_populates="prerequisites",
    )
