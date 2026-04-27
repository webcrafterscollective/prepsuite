from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
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

from app.modules.students.enums import (
    BatchStatus,
    BatchStudentStatus,
    EnrollmentStatus,
    StudentNoteVisibility,
    StudentStatus,
)
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Student(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("tenant_id", "admission_no", name="uq_students_tenant_admission_no"),
        Index("ix_students_tenant_status", "tenant_id", "status"),
        Index("ix_students_tenant_name", "tenant_id", "last_name", "first_name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admission_no: Mapped[str] = mapped_column(String(80), nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StudentStatus.ACTIVE.value,
        server_default=StudentStatus.ACTIVE.value,
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    guardians: Mapped[list[StudentGuardian]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    batch_links: Mapped[list[BatchStudent]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    enrollments: Mapped[list[StudentEnrollment]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list[StudentNote]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list[StudentDocument]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list[StudentStatusHistory]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )


class Guardian(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "guardians"
    __table_args__ = (
        Index("ix_guardians_tenant_phone", "tenant_id", "phone"),
        Index("ix_guardians_tenant_email", "tenant_id", "email"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    relationship_type: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    students: Mapped[list[StudentGuardian]] = relationship(
        back_populates="guardian",
        cascade="all, delete-orphan",
    )


class StudentGuardian(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "student_guardians"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "guardian_id",
            name="uq_student_guardians_tenant_student_guardian",
        ),
        Index("ix_student_guardians_tenant_primary", "tenant_id", "student_id", "is_primary"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardians.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str | None] = mapped_column(String(80))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_pickup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    emergency_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    student: Mapped[Student] = relationship(back_populates="guardians")
    guardian: Mapped[Guardian] = relationship(back_populates="students")


class Batch(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_batches_tenant_code"),
        Index("ix_batches_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    course_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    capacity: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=BatchStatus.DRAFT.value,
        server_default=BatchStatus.DRAFT.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    students: Mapped[list[BatchStudent]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class BatchStudent(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "batch_students"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "batch_id",
            "student_id",
            name="uq_batch_students_membership",
        ),
        Index("ix_batch_students_tenant_status", "tenant_id", "batch_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="CASCADE"),
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
        default=BatchStudentStatus.ACTIVE.value,
        server_default=BatchStudentStatus.ACTIVE.value,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[Batch] = relationship(back_populates="students")
    student: Mapped[Student] = relationship(back_populates="batch_links")


class StudentEnrollment(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "student_enrollments"
    __table_args__ = (
        Index("ix_student_enrollments_tenant_student", "tenant_id", "student_id"),
        Index("ix_student_enrollments_tenant_course", "tenant_id", "course_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EnrollmentStatus.ACTIVE.value,
        server_default=EnrollmentStatus.ACTIVE.value,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[Student] = relationship(back_populates="enrollments")


class StudentNote(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "student_notes"
    __table_args__ = (Index("ix_student_notes_tenant_student", "tenant_id", "student_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note_type: Mapped[str | None] = mapped_column(String(80))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StudentNoteVisibility.INTERNAL.value,
        server_default=StudentNoteVisibility.INTERNAL.value,
    )

    student: Mapped[Student] = relationship(back_populates="notes")


class StudentDocument(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "student_documents"
    __table_args__ = (Index("ix_student_documents_tenant_student", "tenant_id", "student_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    student: Mapped[Student] = relationship(back_populates="documents")


class StudentStatusHistory(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "student_status_history"
    __table_args__ = (Index("ix_student_status_history_tenant_student", "tenant_id", "student_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    student: Mapped[Student] = relationship(back_populates="status_history")
