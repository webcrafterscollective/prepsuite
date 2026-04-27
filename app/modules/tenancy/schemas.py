from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.modules.tenancy.enums import (
    SubscriptionStatus,
    TenantAppStatus,
    TenantDomainVerificationStatus,
    TenantStatus,
    TenantUserStatus,
)
from app.shared.schemas import Schema


def normalize_code(value: str) -> str:
    return value.strip().lower()


class TenantCreate(Schema):
    name: str = Field(min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    status: TenantStatus = TenantStatus.TRIAL
    plan_type: str | None = Field(default=None, max_length=80)
    primary_domain: str | None = Field(default=None, max_length=255)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return normalize_code(value)

    @field_validator("primary_domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        return normalize_code(value) if value else value


class TenantRead(Schema):
    id: uuid.UUID
    name: str
    legal_name: str | None
    slug: str
    status: TenantStatus
    plan_type: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class TenantDomainCreate(Schema):
    domain: str = Field(min_length=1, max_length=255)
    is_primary: bool = False
    verification_status: TenantDomainVerificationStatus = TenantDomainVerificationStatus.PENDING

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return normalize_code(value)


class TenantDomainRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    domain: str
    is_primary: bool
    verification_status: TenantDomainVerificationStatus
    created_at: datetime
    updated_at: datetime


class AppCatalogCreate(Schema):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,78}[a-z0-9]$")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    category: str = Field(min_length=1, max_length=80)
    is_core: bool = False
    is_active: bool = True

    @field_validator("code", "category")
    @classmethod
    def normalize_catalog_fields(cls, value: str) -> str:
        return normalize_code(value)


class AppCatalogRead(Schema):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    category: str
    is_core: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenantAppUpsert(Schema):
    status: TenantAppStatus = TenantAppStatus.ENABLED
    subscription_status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class TenantAppRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    app_code: str
    status: TenantAppStatus
    subscription_status: SubscriptionStatus
    starts_at: datetime | None
    ends_at: datetime | None
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TenantSettingsUpdate(Schema):
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    locale: str | None = Field(default=None, min_length=1, max_length=16)
    general_settings: dict[str, Any] | None = None
    notification_preferences: dict[str, Any] | None = None


class TenantSettingsRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    timezone: str
    locale: str
    general_settings: dict[str, Any]
    notification_preferences: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TenantBrandingUpdate(Schema):
    logo_url: str | None = None
    primary_color: str | None = Field(default=None, max_length=32)
    secondary_color: str | None = Field(default=None, max_length=32)
    accent_color: str | None = Field(default=None, max_length=32)
    branding_settings: dict[str, Any] | None = None


class TenantBrandingRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    logo_url: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None
    branding_settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TenantUserCreate(Schema):
    user_id: uuid.UUID
    status: TenantUserStatus = TenantUserStatus.ACTIVE
    is_primary_admin: bool = False


class TenantUserRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    status: TenantUserStatus
    is_primary_admin: bool
    created_at: datetime
    updated_at: datetime


class TenantContextRead(Schema):
    tenant_id: uuid.UUID
    source: str
    tenant: TenantRead
