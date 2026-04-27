from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.tenancy.enums import (
    SubscriptionStatus,
    TenantAppStatus,
    TenantDomainVerificationStatus,
    TenantStatus,
    TenantUserStatus,
)
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenants_slug"),
        Index("ix_tenants_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TenantStatus.TRIAL.value,
        server_default=TenantStatus.TRIAL.value,
    )
    plan_type: Mapped[str | None] = mapped_column(String(80))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    domains: Mapped[list[TenantDomain]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    apps: Mapped[list[TenantApp]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    settings: Mapped[TenantSettings | None] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    branding: Mapped[TenantBranding | None] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    users: Mapped[list[TenantUser]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class TenantDomain(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_domains"
    __table_args__ = (
        UniqueConstraint("domain", name="uq_tenant_domains_domain"),
        UniqueConstraint("tenant_id", "domain", name="uq_tenant_domains_tenant_id_domain"),
        Index("ix_tenant_domains_tenant_primary", "tenant_id", "is_primary"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TenantDomainVerificationStatus.PENDING.value,
        server_default=TenantDomainVerificationStatus.PENDING.value,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="domains")


class AppCatalog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "app_catalog"
    __table_args__ = (
        UniqueConstraint("code", name="uq_app_catalog_code"),
        Index("ix_app_catalog_category", "category"),
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant_apps: Mapped[list[TenantApp]] = relationship(back_populates="catalog_app")


class TenantApp(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_apps"
    __table_args__ = (
        UniqueConstraint("tenant_id", "app_code", name="uq_tenant_apps_tenant_id_app_code"),
        Index("ix_tenant_apps_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    app_code: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("app_catalog.code", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TenantAppStatus.DISABLED.value,
        server_default=TenantAppStatus.DISABLED.value,
    )
    subscription_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SubscriptionStatus.TRIAL.value,
        server_default=SubscriptionStatus.TRIAL.value,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="apps")
    catalog_app: Mapped[AppCatalog] = relationship(back_populates="tenant_apps")


class TenantSettings(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="UTC",
        server_default="UTC",
    )
    locale: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="en",
        server_default="en",
    )
    general_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    notification_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="settings")


class TenantBranding(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_branding"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_branding_tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    logo_url: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str | None] = mapped_column(String(32))
    secondary_color: Mapped[str | None] = mapped_column(String(32))
    accent_color: Mapped[str | None] = mapped_column(String(32))
    branding_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="branding")


class TenantUser(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_id_user_id"),
        Index("ix_tenant_users_user_id", "user_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TenantUserStatus.ACTIVE.value,
        server_default=TenantUserStatus.ACTIVE.value,
    )
    is_primary_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped[Tenant] = relationship(back_populates="users")
