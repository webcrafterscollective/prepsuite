from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
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

from app.modules.attend.enums import (
    AttendanceCorrectionStatus,
    AttendancePolicyScope,
    AttendancePolicyStatus,
    EmployeeAttendanceSource,
    EmployeeAttendanceStatus,
    StudentAttendanceSessionStatus,
    StudentAttendanceStatus,
)
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class StudentAttendanceSession(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "student_attendance_sessions"
    __table_args__ = (
        Index("ix_student_attendance_sessions_tenant_batch", "tenant_id", "batch_id"),
        Index("ix_student_attendance_sessions_tenant_date", "tenant_id", "date"),
        Index("ix_student_attendance_sessions_tenant_status", "tenant_id", "status"),
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
    course_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    live_class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    marked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StudentAttendanceSessionStatus.OPEN.value,
        server_default=StudentAttendanceSessionStatus.OPEN.value,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    records: Mapped[list[StudentAttendanceRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class StudentAttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "student_attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "session_id",
            "student_id",
            name="uq_student_attendance_records_session_student",
        ),
        Index("ix_student_attendance_records_tenant_session", "tenant_id", "session_id"),
        Index("ix_student_attendance_records_tenant_student", "tenant_id", "student_id"),
        Index("ix_student_attendance_records_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_attendance_sessions.id", ondelete="CASCADE"),
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
        default=StudentAttendanceStatus.PRESENT.value,
        server_default=StudentAttendanceStatus.PRESENT.value,
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    marked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    remarks: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    session: Mapped[StudentAttendanceSession] = relationship(back_populates="records")


class EmployeeAttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "employee_attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "employee_id",
            "date",
            name="uq_employee_attendance_records_employee_date",
        ),
        Index("ix_employee_attendance_records_tenant_employee", "tenant_id", "employee_id"),
        Index("ix_employee_attendance_records_tenant_date", "tenant_id", "date"),
        Index("ix_employee_attendance_records_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EmployeeAttendanceStatus.PRESENT.value,
        server_default=EmployeeAttendanceStatus.PRESENT.value,
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EmployeeAttendanceSource.MANUAL.value,
        server_default=EmployeeAttendanceSource.MANUAL.value,
    )
    marked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    remarks: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class AttendanceCorrectionRequest(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "attendance_correction_requests"
    __table_args__ = (
        Index("ix_attendance_correction_requests_tenant_status", "tenant_id", "status"),
        Index(
            "ix_attendance_correction_requests_tenant_requester",
            "tenant_id",
            "requester_user_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    student_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_attendance_records.id", ondelete="CASCADE"),
    )
    employee_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employee_attendance_records.id", ondelete="CASCADE"),
    )
    requested_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AttendanceCorrectionStatus.PENDING.value,
        server_default=AttendanceCorrectionStatus.PENDING.value,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class AttendancePolicy(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "attendance_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_attendance_policies_tenant_code"),
        Index("ix_attendance_policies_tenant_scope", "tenant_id", "scope"),
        Index("ix_attendance_policies_tenant_default", "tenant_id", "is_default"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AttendancePolicyScope.ALL.value,
        server_default=AttendancePolicyScope.ALL.value,
    )
    minimum_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("75.00"),
        server_default=text("75.00"),
    )
    late_after_minutes: Mapped[int | None] = mapped_column(Integer)
    absent_after_minutes: Mapped[int | None] = mapped_column(Integer)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AttendancePolicyStatus.ACTIVE.value,
        server_default=AttendancePolicyStatus.ACTIVE.value,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
