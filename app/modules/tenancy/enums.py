from __future__ import annotations

from enum import StrEnum


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CANCELLED = "cancelled"


class TenantDomainVerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class TenantAppStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    LOCKED = "locked"
    TRIAL = "trial"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    TRIAL = "trial"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TenantUserStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    DISABLED = "disabled"
