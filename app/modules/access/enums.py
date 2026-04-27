from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


class UserType(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    INSTITUTION_ADMIN = "institution_admin"
    EMPLOYEE = "employee"
    TEACHER = "teacher"
    STUDENT = "student"
    GUARDIAN = "guardian"


class RefreshTokenStatus(StrEnum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    REUSED = "reused"


class LoginSessionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"
    REVOKED = "revoked"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"
