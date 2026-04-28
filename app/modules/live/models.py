from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
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

from app.modules.live.enums import (
    LiveClassStatus,
    LiveInviteStatus,
    LiveJoinStatus,
    LiveParticipantRole,
    LiveProvider,
    LiveRecordingStatus,
)
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LiveClass(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "live_classes"
    __table_args__ = (
        UniqueConstraint("class_code", name="uq_live_classes_class_code"),
        Index("ix_live_classes_tenant_batch", "tenant_id", "batch_id"),
        Index("ix_live_classes_tenant_instructor", "tenant_id", "instructor_id"),
        Index("ix_live_classes_tenant_status", "tenant_id", "status"),
        Index("ix_live_classes_tenant_starts", "tenant_id", "starts_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_code: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="SET NULL"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    join_before_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=15,
        server_default=text("15"),
    )
    join_after_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=15,
        server_default=text("15"),
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LiveClassStatus.SCHEDULED.value,
        server_default=LiveClassStatus.SCHEDULED.value,
    )
    live_provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LiveProvider.MEDIASOUP.value,
        server_default=LiveProvider.MEDIASOUP.value,
    )
    live_room_id: Mapped[str | None] = mapped_column(String(160))
    link: Mapped[str] = mapped_column(Text, nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    participants: Mapped[list[LiveClassParticipant]] = relationship(
        back_populates="live_class",
        cascade="all, delete-orphan",
    )
    invites: Mapped[list[LiveClassInvite]] = relationship(
        back_populates="live_class",
        cascade="all, delete-orphan",
    )
    recordings: Mapped[list[LiveClassRecording]] = relationship(
        back_populates="live_class",
        cascade="all, delete-orphan",
    )
    events: Mapped[list[LiveClassEvent]] = relationship(
        back_populates="live_class",
        cascade="all, delete-orphan",
    )


class LiveClassParticipant(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "live_class_participants"
    __table_args__ = (
        Index("ix_live_class_participants_tenant_class", "tenant_id", "live_class_id"),
        Index("ix_live_class_participants_tenant_user", "tenant_id", "user_id"),
        Index("ix_live_class_participants_tenant_student", "tenant_id", "student_id"),
        Index("ix_live_class_participants_tenant_employee", "tenant_id", "employee_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    live_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
    )
    participant_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LiveParticipantRole.STUDENT.value,
        server_default=LiveParticipantRole.STUDENT.value,
    )
    join_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LiveJoinStatus.ALLOWED.value,
        server_default=LiveJoinStatus.ALLOWED.value,
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    live_class: Mapped[LiveClass] = relationship(back_populates="participants")


class LiveClassInvite(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "live_class_invites"
    __table_args__ = (
        UniqueConstraint("tenant_id", "live_class_id", "email", name="uq_live_class_invites_email"),
        Index("ix_live_class_invites_tenant_class", "tenant_id", "live_class_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    live_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str | None] = mapped_column(String(128))
    participant_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LiveParticipantRole.GUEST.value,
        server_default=LiveParticipantRole.GUEST.value,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LiveInviteStatus.PENDING.value,
        server_default=LiveInviteStatus.PENDING.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    live_class: Mapped[LiveClass] = relationship(back_populates="invites")


class LiveClassAttendanceSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "live_class_attendance_snapshots"
    __table_args__ = (
        Index("ix_live_class_attendance_snapshots_tenant_class", "tenant_id", "live_class_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    live_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class LiveClassRecording(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "live_class_recordings"
    __table_args__ = (
        Index("ix_live_class_recordings_tenant_class", "tenant_id", "live_class_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    live_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_recording_id: Mapped[str | None] = mapped_column(String(160))
    storage_key: Mapped[str | None] = mapped_column(Text)
    playback_url: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LiveRecordingStatus.PROCESSING.value,
        server_default=LiveRecordingStatus.PROCESSING.value,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    live_class: Mapped[LiveClass] = relationship(back_populates="recordings")


class LiveClassEvent(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "live_class_events"
    __table_args__ = (
        Index("ix_live_class_events_tenant_class", "tenant_id", "live_class_id"),
        Index("ix_live_class_events_tenant_type", "tenant_id", "event_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    live_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_class_participants.id", ondelete="SET NULL"),
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    live_class: Mapped[LiveClass] = relationship(back_populates="events")
