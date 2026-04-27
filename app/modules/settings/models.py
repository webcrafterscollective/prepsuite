from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.settings.enums import AcademicYearStatus, IntegrationStatus, RuleStatus
from app.shared.models import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TenantAcademicYear(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_academic_years"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tenant_academic_years_tenant_code"),
        Index("ix_tenant_academic_years_tenant_status", "tenant_id", "status"),
        Index("ix_tenant_academic_years_tenant_current", "tenant_id", "is_current"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AcademicYearStatus.DRAFT.value,
        server_default=AcademicYearStatus.DRAFT.value,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class TenantGradingRule(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_grading_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tenant_grading_rules_tenant_code"),
        Index("ix_tenant_grading_rules_tenant_default", "tenant_id", "is_default"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="Default grading")
    grade_scale: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    pass_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    rounding_strategy: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RuleStatus.ACTIVE.value,
        server_default=RuleStatus.ACTIVE.value,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class TenantAttendanceRule(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_attendance_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tenant_attendance_rules_tenant_code"),
        Index("ix_tenant_attendance_rules_tenant_default", "tenant_id", "is_default"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="Default attendance")
    minimum_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    late_threshold_minutes: Mapped[int | None] = mapped_column()
    absent_after_minutes: Mapped[int | None] = mapped_column()
    rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RuleStatus.ACTIVE.value,
        server_default=RuleStatus.ACTIVE.value,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class TenantIntegration(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_integrations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_integrations_tenant_provider"),
        Index("ix_tenant_integrations_tenant_type", "tenant_id", "integration_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    integration_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=IntegrationStatus.DISABLED.value,
        server_default=IntegrationStatus.DISABLED.value,
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    secrets_ref: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class TenantAppSetting(UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "tenant_app_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "app_code", name="uq_tenant_app_settings_tenant_app"),
        Index("ix_tenant_app_settings_tenant_enabled", "tenant_id", "enabled_by_tenant"),
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
    enabled_by_tenant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
