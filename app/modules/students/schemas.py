from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.pagination import CursorPage
from app.modules.students.enums import (
    BatchStatus,
    BatchStudentStatus,
    EnrollmentStatus,
    Gender,
    StudentNoteVisibility,
    StudentStatus,
)
from app.shared.schemas import Schema


def normalize_code(value: str) -> str:
    return value.strip().lower()


def normalize_email(value: str | None) -> str | None:
    return value.strip().lower() if value else value


class StudentCreate(Schema):
    admission_no: str = Field(min_length=1, max_length=80)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    date_of_birth: date | None = None
    gender: Gender | None = None
    status: StudentStatus = StudentStatus.ACTIVE
    joined_at: datetime | None = None

    @field_validator("admission_no")
    @classmethod
    def normalize_admission_no(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str | None) -> str | None:
        return normalize_email(value)


class StudentUpdate(Schema):
    admission_no: str | None = Field(default=None, min_length=1, max_length=80)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    date_of_birth: date | None = None
    gender: Gender | None = None
    status: StudentStatus | None = None
    status_change_reason: str | None = Field(default=None, max_length=500)

    @field_validator("admission_no")
    @classmethod
    def normalize_admission_no(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str | None) -> str | None:
        return normalize_email(value)


class StudentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    admission_no: str
    first_name: str
    last_name: str | None
    email: EmailStr | None
    phone: str | None
    date_of_birth: date | None
    gender: Gender | None
    status: StudentStatus
    joined_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class StudentPage(CursorPage[StudentRead]):
    pass


class StudentBulkImportItem(StudentCreate):
    pass


class StudentBulkImportRequest(Schema):
    students: list[StudentBulkImportItem] = Field(min_length=1, max_length=500)


class StudentBulkImportError(Schema):
    index: int
    admission_no: str | None
    code: str
    message: str


class StudentBulkImportResponse(Schema):
    created: list[StudentRead]
    errors: list[StudentBulkImportError]


class GuardianCreate(Schema):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    relationship_type: str | None = Field(default=None, max_length=80)
    address: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_primary: bool = False
    can_pickup: bool = False
    emergency_contact: bool = False

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str | None) -> str | None:
        return normalize_email(value)


class GuardianRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    first_name: str
    last_name: str | None
    email: EmailStr | None
    phone: str | None
    relationship_type: str | None
    address: str | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class StudentGuardianRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    guardian_id: uuid.UUID
    relationship_type: str | None
    is_primary: bool
    can_pickup: bool
    emergency_contact: bool
    guardian: GuardianRead


class BatchCreate(Schema):
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,78}[a-z0-9]$")
    course_id: uuid.UUID | None = None
    start_date: date
    end_date: date | None = None
    capacity: int | None = Field(default=None, ge=1)
    status: BatchStatus = BatchStatus.DRAFT

    @field_validator("code")
    @classmethod
    def normalize_batch_code(cls, value: str) -> str:
        return normalize_code(value)

    @model_validator(mode="after")
    def validate_dates(self) -> BatchCreate:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class BatchUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    course_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    capacity: int | None = Field(default=None, ge=1)
    status: BatchStatus | None = None


class BatchRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    code: str
    course_id: uuid.UUID | None
    start_date: date
    end_date: date | None
    capacity: int | None
    status: BatchStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BatchStudentAddRequest(Schema):
    student_id: uuid.UUID


class BatchStudentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    batch_id: uuid.UUID
    student_id: uuid.UUID
    status: BatchStudentStatus
    joined_at: datetime
    left_at: datetime | None


class StudentEnrollmentCreate(Schema):
    course_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE


class StudentEnrollmentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    course_id: uuid.UUID
    batch_id: uuid.UUID | None
    status: EnrollmentStatus
    enrolled_at: datetime
    completed_at: datetime | None


class StudentNoteCreate(Schema):
    body: str = Field(min_length=1)
    note_type: str | None = Field(default=None, max_length=80)
    visibility: StudentNoteVisibility = StudentNoteVisibility.INTERNAL


class StudentNoteRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    author_user_id: uuid.UUID | None
    note_type: str | None
    body: str
    visibility: StudentNoteVisibility
    created_at: datetime


class StudentDocumentCreate(Schema):
    title: str = Field(min_length=1, max_length=160)
    document_type: str | None = Field(default=None, max_length=80)
    storage_key: str = Field(min_length=1)
    file_name: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudentDocumentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    title: str
    document_type: str | None
    storage_key: str
    file_name: str | None
    mime_type: str | None
    size_bytes: int | None
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    uploaded_by: uuid.UUID | None
    created_at: datetime


class StudentStatusHistoryRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    student_id: uuid.UUID
    from_status: StudentStatus | None
    to_status: StudentStatus
    reason: str | None
    changed_by: uuid.UUID | None
    created_at: datetime


class StudentTimelineEvent(Schema):
    event_type: str
    event_id: uuid.UUID
    occurred_at: datetime
    title: str
    details: dict[str, Any] = Field(default_factory=dict)


class StudentProfileRead(Schema):
    student: StudentRead
    guardians: list[StudentGuardianRead]
    batches: list[BatchStudentRead]
    enrollments: list[StudentEnrollmentRead]
    notes: list[StudentNoteRead]
    documents: list[StudentDocumentRead]
    status_history: list[StudentStatusHistoryRead]
