from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from app.core.pagination import CursorPage
from app.modules.live.enums import (
    LiveClassStatus,
    LiveJoinStatus,
    LiveParticipantRole,
    LiveProvider,
    LiveRecordingStatus,
)
from app.shared.schemas import Schema


class LiveClassCreate(Schema):
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    course_id: uuid.UUID | None = None
    batch_id: uuid.UUID
    instructor_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int = Field(ge=1, le=1440)
    join_before_minutes: int = Field(default=15, ge=0, le=240)
    join_after_minutes: int = Field(default=15, ge=0, le=240)
    capacity: int = Field(ge=1, le=10000)
    settings: dict[str, Any] = Field(default_factory=dict)
    admin_override: bool = False

    @model_validator(mode="after")
    def validate_time_window(self) -> LiveClassCreate:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class LiveClassUpdate(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    course_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    instructor_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    join_before_minutes: int | None = Field(default=None, ge=0, le=240)
    join_after_minutes: int | None = Field(default=None, ge=0, le=240)
    capacity: int | None = Field(default=None, ge=1, le=10000)
    settings: dict[str, Any] | None = None
    admin_override: bool = False


class LiveClassCancelRequest(Schema):
    reason: str | None = None


class LiveClassRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    class_code: str
    title: str
    description: str | None
    course_id: uuid.UUID | None
    batch_id: uuid.UUID
    instructor_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    join_before_minutes: int
    join_after_minutes: int
    capacity: int
    status: LiveClassStatus
    live_provider: LiveProvider
    live_room_id: str | None
    link: str
    settings: dict[str, Any]
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class LiveClassPage(CursorPage[LiveClassRead]):
    pass


class LiveClassParticipantRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    live_class_id: uuid.UUID
    user_id: uuid.UUID | None
    student_id: uuid.UUID | None
    employee_id: uuid.UUID | None
    participant_role: LiveParticipantRole
    join_status: LiveJoinStatus
    joined_at: datetime | None
    left_at: datetime | None
    total_duration_seconds: int
    created_at: datetime
    updated_at: datetime


class LiveClassEventRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    live_class_id: uuid.UUID
    participant_id: uuid.UUID | None
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LiveClassRecordingCreate(Schema):
    provider_recording_id: str | None = Field(default=None, max_length=160)
    storage_key: str | None = None
    playback_url: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    status: LiveRecordingStatus = LiveRecordingStatus.PROCESSING
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiveClassRecordingRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    live_class_id: uuid.UUID
    provider_recording_id: str | None
    storage_key: str | None
    playback_url: str | None
    duration_seconds: int | None
    status: LiveRecordingStatus
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class LiveClassDetailRead(Schema):
    live_class: LiveClassRead
    participants: list[LiveClassParticipantRead]
    recordings: list[LiveClassRecordingRead]
    events: list[LiveClassEventRead]


class LiveAccessValidationRequest(Schema):
    user_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None
    participant_role: LiveParticipantRole | None = None
    now: datetime | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> LiveAccessValidationRequest:
        if self.student_id is None and self.employee_id is None and self.user_id is None:
            raise ValueError("at least one user_id, student_id, or employee_id is required")
        return self


class LiveAccessValidationRead(Schema):
    allowed: bool
    reason: str | None = None
    live_class: LiveClassRead
    participant: LiveClassParticipantRead | None = None
    join_window_starts_at: datetime
    join_window_ends_at: datetime


class LiveAttendanceEventItem(Schema):
    event_type: str = Field(pattern=r"^live\.participant\.(joined|left)$")
    user_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None
    participant_role: LiveParticipantRole = LiveParticipantRole.STUDENT
    occurred_at: datetime | None = None
    total_duration_seconds: int | None = Field(default=None, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


class LiveAttendanceEventsRequest(Schema):
    events: list[LiveAttendanceEventItem] = Field(min_length=1, max_length=500)
    snapshot: dict[str, Any] | None = None


class LiveAttendanceEventsRead(Schema):
    processed: int
    events: list[LiveClassEventRead]
    participants: list[LiveClassParticipantRead]
