from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from app.modules.attend.enums import (
    AttendanceCorrectionStatus,
    AttendanceCorrectionTarget,
    EmployeeAttendanceSource,
    EmployeeAttendanceStatus,
    StudentAttendanceSessionStatus,
    StudentAttendanceStatus,
)
from app.shared.schemas import Schema


class StudentAttendanceSessionCreate(Schema):
    batch_id: uuid.UUID
    date: date
    course_id: uuid.UUID | None = None
    live_class_id: uuid.UUID | None = None
    status: StudentAttendanceSessionStatus = StudentAttendanceSessionStatus.OPEN
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudentAttendanceSessionRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    batch_id: uuid.UUID
    course_id: uuid.UUID | None
    live_class_id: uuid.UUID | None
    date: date
    marked_by: uuid.UUID | None
    status: StudentAttendanceSessionStatus
    submitted_at: datetime | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class StudentAttendanceRecordMark(Schema):
    student_id: uuid.UUID
    status: StudentAttendanceStatus
    remarks: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudentAttendanceRecordsRequest(Schema):
    records: list[StudentAttendanceRecordMark] = Field(min_length=1, max_length=500)
    submit_session: bool = False

    @model_validator(mode="after")
    def validate_unique_students(self) -> StudentAttendanceRecordsRequest:
        student_ids = [record.student_id for record in self.records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError("student_id values must be unique")
        return self


class StudentAttendanceRecordUpdate(Schema):
    status: StudentAttendanceStatus | None = None
    remarks: str | None = None
    metadata: dict[str, Any] | None = None


class StudentAttendanceRecordRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    session_id: uuid.UUID
    student_id: uuid.UUID
    status: StudentAttendanceStatus
    marked_at: datetime
    marked_by: uuid.UUID | None
    remarks: str | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class StudentAttendanceSummaryItem(Schema):
    student_id: uuid.UUID
    total_records: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    attendance_percentage: Decimal


class StudentAttendanceSummaryRead(Schema):
    start_date: date
    end_date: date
    batch_id: uuid.UUID | None
    student_id: uuid.UUID | None
    items: list[StudentAttendanceSummaryItem]


class EmployeeCheckInRequest(Schema):
    employee_id: uuid.UUID
    check_in_at: datetime | None = None
    source: EmployeeAttendanceSource = EmployeeAttendanceSource.MANUAL
    remarks: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmployeeCheckOutRequest(Schema):
    employee_id: uuid.UUID
    check_out_at: datetime | None = None
    status: EmployeeAttendanceStatus | None = None
    remarks: str | None = None


class EmployeeAttendanceRecordRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    date: date
    check_in_at: datetime | None
    check_out_at: datetime | None
    status: EmployeeAttendanceStatus
    source: EmployeeAttendanceSource
    marked_by: uuid.UUID | None
    remarks: str | None
    idempotency_key: str | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class EmployeeAttendanceSummaryItem(Schema):
    employee_id: uuid.UUID
    total_days: int
    present_count: int
    late_count: int
    absent_count: int
    half_day_count: int
    on_leave_count: int
    attendance_percentage: Decimal
    total_work_seconds: int


class EmployeeAttendanceSummaryRead(Schema):
    start_date: date
    end_date: date
    employee_id: uuid.UUID | None
    items: list[EmployeeAttendanceSummaryItem]


class AttendanceCorrectionCreate(Schema):
    target_type: AttendanceCorrectionTarget
    student_record_id: uuid.UUID | None = None
    employee_record_id: uuid.UUID | None = None
    requested_status: str = Field(min_length=1, max_length=32)
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_target(self) -> AttendanceCorrectionCreate:
        if (
            self.target_type == AttendanceCorrectionTarget.STUDENT_RECORD
            and (self.student_record_id is None or self.employee_record_id is not None)
        ):
            raise ValueError("student_record corrections require only student_record_id")
        if (
            self.target_type == AttendanceCorrectionTarget.EMPLOYEE_RECORD
            and (self.employee_record_id is None or self.student_record_id is not None)
        ):
            raise ValueError("employee_record corrections require only employee_record_id")
        return self


class AttendanceCorrectionApproveRequest(Schema):
    approved: bool = True
    reviewer_note: str | None = None


class AttendanceCorrectionRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    requester_user_id: uuid.UUID | None
    target_type: AttendanceCorrectionTarget
    student_record_id: uuid.UUID | None
    employee_record_id: uuid.UUID | None
    requested_status: str
    reason: str
    status: AttendanceCorrectionStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    reviewer_note: str | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime
