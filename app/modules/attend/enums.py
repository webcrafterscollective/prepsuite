from __future__ import annotations

from enum import StrEnum


class StudentAttendanceSessionStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    SUBMITTED = "submitted"
    LOCKED = "locked"
    CANCELLED = "cancelled"


class StudentAttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class EmployeeAttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    HALF_DAY = "half_day"
    ON_LEAVE = "on_leave"


class EmployeeAttendanceSource(StrEnum):
    MANUAL = "manual"
    BIOMETRIC = "biometric"
    LIVE_CLASS = "live_class"
    IMPORT = "import"


class AttendanceCorrectionTarget(StrEnum):
    STUDENT_RECORD = "student_record"
    EMPLOYEE_RECORD = "employee_record"


class AttendanceCorrectionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AttendancePolicyScope(StrEnum):
    STUDENT = "student"
    EMPLOYEE = "employee"
    ALL = "all"


class AttendancePolicyStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
