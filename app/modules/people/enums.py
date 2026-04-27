from __future__ import annotations

from enum import StrEnum


class EmployeeType(StrEnum):
    TEACHER = "teacher"
    ADMIN = "admin"
    COUNSELLOR = "counsellor"
    ACCOUNTANT = "accountant"
    SUPPORT = "support"
    MANAGER = "manager"


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class DepartmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class TeacherAssignmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EmployeeNoteVisibility(StrEnum):
    INTERNAL = "internal"
    MANAGERS = "managers"
    HR = "hr"
