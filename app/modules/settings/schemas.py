from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.modules.settings.enums import AcademicYearStatus, IntegrationStatus, RuleStatus
from app.modules.tenancy.enums import SubscriptionStatus, TenantAppStatus
from app.shared.schemas import Schema


def normalize_code(value: str) -> str:
    return value.strip().lower()


class GeneralSettingsRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    timezone: str
    locale: str
    general_settings: dict[str, Any]
    notification_preferences: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class GeneralSettingsUpdate(Schema):
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    locale: str | None = Field(default=None, min_length=1, max_length=16)
    general_settings: dict[str, Any] | None = None
    notification_preferences: dict[str, Any] | None = None


class BrandingSettingsRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    logo_url: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None
    branding_settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BrandingSettingsUpdate(Schema):
    logo_url: str | None = None
    primary_color: str | None = Field(default=None, max_length=32)
    secondary_color: str | None = Field(default=None, max_length=32)
    accent_color: str | None = Field(default=None, max_length=32)
    branding_settings: dict[str, Any] | None = None


class AppSettingsToggleRequest(Schema):
    enabled: bool
    settings: dict[str, Any] | None = None


class AppSettingsRead(Schema):
    app_code: str
    name: str | None = None
    category: str | None = None
    is_core: bool = False
    is_active: bool = True
    tenant_app_status: TenantAppStatus | None = None
    subscription_status: SubscriptionStatus | None = None
    enabled_by_tenant: bool
    can_enable: bool
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class AcademicYearCreate(Schema):
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,78}[a-z0-9]$")
    starts_on: date
    ends_on: date
    status: AcademicYearStatus = AcademicYearStatus.DRAFT
    is_current: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def normalize_academic_year_code(cls, value: str) -> str:
        return normalize_code(value)

    @model_validator(mode="after")
    def validate_date_range(self) -> AcademicYearCreate:
        if self.ends_on <= self.starts_on:
            raise ValueError("ends_on must be after starts_on")
        return self


class AcademicYearUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    starts_on: date | None = None
    ends_on: date | None = None
    status: AcademicYearStatus | None = None
    is_current: bool | None = None
    settings: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> AcademicYearUpdate:
        if (
            self.starts_on is not None
            and self.ends_on is not None
            and self.ends_on <= self.starts_on
        ):
            raise ValueError("ends_on must be after starts_on")
        return self


class AcademicYearRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    code: str
    starts_on: date
    ends_on: date
    status: AcademicYearStatus
    is_current: bool
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class GradingRuleUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    grade_scale: dict[str, Any] | None = None
    pass_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    rounding_strategy: str | None = Field(default=None, max_length=40)
    status: RuleStatus | None = None


class GradingRuleRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    grade_scale: dict[str, Any]
    pass_percentage: Decimal | None
    rounding_strategy: str | None
    status: RuleStatus
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AttendanceRuleUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    minimum_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    late_threshold_minutes: int | None = Field(default=None, ge=0)
    absent_after_minutes: int | None = Field(default=None, ge=0)
    rules: dict[str, Any] | None = None
    status: RuleStatus | None = None


class AttendanceRuleRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    minimum_percentage: Decimal | None
    late_threshold_minutes: int | None
    absent_after_minutes: int | None
    rules: dict[str, Any]
    status: RuleStatus
    is_default: bool
    created_at: datetime
    updated_at: datetime


class IntegrationSettingsRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    provider: str
    integration_type: str
    status: IntegrationStatus
    config: dict[str, Any]
    secrets_ref: str | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime
