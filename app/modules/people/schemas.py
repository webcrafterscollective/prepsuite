from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.pagination import CursorPage
from app.modules.people.enums import (
    DepartmentStatus,
    EmployeeNoteVisibility,
    EmployeeStatus,
    EmployeeType,
    TeacherAssignmentStatus,
)
from app.shared.schemas import Schema


def normalize_code(value: str) -> str:
    return value.strip().lower()


def normalize_email(value: str | None) -> str | None:
    return value.strip().lower() if value else value


class DepartmentCreate(Schema):
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,78}[a-z0-9]$")
    description: str | None = None
    status: DepartmentStatus = DepartmentStatus.ACTIVE

    @field_validator("code")
    @classmethod
    def normalize_department_code(cls, value: str) -> str:
        return normalize_code(value)


class DepartmentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    code: str
    description: str | None
    status: DepartmentStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class EmployeeProfileUpsert(Schema):
    job_title: str | None = Field(default=None, max_length=160)
    bio: str | None = None
    qualifications: dict[str, Any] = Field(default_factory=dict)
    emergency_contact: dict[str, Any] = Field(default_factory=dict)
    profile_data: dict[str, Any] = Field(default_factory=dict)


class EmployeeProfileRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    job_title: str | None
    bio: str | None
    qualifications: dict[str, Any]
    emergency_contact: dict[str, Any]
    profile_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EmployeeCreate(Schema):
    user_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    employee_code: str = Field(min_length=1, max_length=80)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    employee_type: EmployeeType = EmployeeType.TEACHER
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    joined_at: datetime | None = None
    profile: EmployeeProfileUpsert | None = None

    @field_validator("employee_code")
    @classmethod
    def normalize_employee_code(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str | None) -> str | None:
        return normalize_email(value)


class EmployeeUpdate(Schema):
    user_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    employee_code: str | None = Field(default=None, min_length=1, max_length=80)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    employee_type: EmployeeType | None = None
    status: EmployeeStatus | None = None
    joined_at: datetime | None = None
    status_change_reason: str | None = Field(default=None, max_length=500)
    profile: EmployeeProfileUpsert | None = None

    @field_validator("employee_code")
    @classmethod
    def normalize_employee_code(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str | None) -> str | None:
        return normalize_email(value)


class EmployeeRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    department_id: uuid.UUID | None
    employee_code: str
    first_name: str
    last_name: str | None
    email: EmailStr | None
    phone: str | None
    employee_type: EmployeeType
    status: EmployeeStatus
    joined_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class EmployeePage(CursorPage[EmployeeRead]):
    pass


class EmployeeDocumentCreate(Schema):
    title: str = Field(min_length=1, max_length=160)
    document_type: str | None = Field(default=None, max_length=80)
    storage_key: str = Field(min_length=1)
    file_name: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmployeeDocumentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
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


class EmployeeNoteCreate(Schema):
    body: str = Field(min_length=1)
    note_type: str | None = Field(default=None, max_length=80)
    visibility: EmployeeNoteVisibility = EmployeeNoteVisibility.INTERNAL


class EmployeeNoteRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    author_user_id: uuid.UUID | None
    note_type: str | None
    body: str
    visibility: EmployeeNoteVisibility
    created_at: datetime


class EmployeeStatusHistoryRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    employee_id: uuid.UUID
    from_status: EmployeeStatus | None
    to_status: EmployeeStatus
    reason: str | None
    changed_by: uuid.UUID | None
    created_at: datetime


class TeacherAssignmentCreate(Schema):
    teacher_id: uuid.UUID
    course_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    assignment_type: str = Field(min_length=1, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: TeacherAssignmentStatus = TeacherAssignmentStatus.ACTIVE

    @model_validator(mode="after")
    def validate_assignment_target(self) -> TeacherAssignmentCreate:
        if self.course_id is None and self.batch_id is None:
            raise ValueError("Either course_id or batch_id is required")
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at < self.starts_at
        ):
            raise ValueError("ends_at must be on or after starts_at")
        return self


class TeacherAssignmentRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    teacher_id: uuid.UUID
    course_id: uuid.UUID | None
    batch_id: uuid.UUID | None
    assignment_type: str
    starts_at: datetime | None
    ends_at: datetime | None
    status: TeacherAssignmentStatus
    created_at: datetime
    updated_at: datetime


class TeacherWorkloadRead(Schema):
    teacher_id: uuid.UUID
    active_assignment_count: int
    course_count: int
    batch_count: int
    assignments: list[TeacherAssignmentRead]


class EmployeeTimelineEvent(Schema):
    event_type: str
    event_id: uuid.UUID
    occurred_at: datetime
    title: str
    details: dict[str, Any] = Field(default_factory=dict)


class EmployeeProfileAggregateRead(Schema):
    employee: EmployeeRead
    profile: EmployeeProfileRead | None
    department: DepartmentRead | None
    documents: list[EmployeeDocumentRead]
    notes: list[EmployeeNoteRead]
    status_history: list[EmployeeStatusHistoryRead]
    teacher_assignments: list[TeacherAssignmentRead]
