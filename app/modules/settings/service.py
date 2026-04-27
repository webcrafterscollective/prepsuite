from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import (
    TenantContext,
    ensure_tenant_access,
    set_current_tenant_in_session,
)
from app.modules.settings.enums import RuleStatus
from app.modules.settings.models import (
    TenantAcademicYear,
    TenantAppSetting,
    TenantAttendanceRule,
    TenantGradingRule,
)
from app.modules.settings.repository import (
    TenantAcademicYearRepository,
    TenantAppSettingRepository,
    TenantAttendanceRuleRepository,
    TenantGradingRuleRepository,
    TenantIntegrationRepository,
)
from app.modules.settings.schemas import (
    AcademicYearCreate,
    AcademicYearUpdate,
    AppSettingsToggleRequest,
    AttendanceRuleUpdate,
    BrandingSettingsUpdate,
    GeneralSettingsUpdate,
    GradingRuleUpdate,
)
from app.modules.tenancy.enums import SubscriptionStatus, TenantAppStatus
from app.modules.tenancy.models import AppCatalog, TenantApp, TenantBranding, TenantSettings
from app.modules.tenancy.repository import (
    AppCatalogRepository,
    TenantAppRepository,
    TenantBrandingRepository,
    TenantSettingsRepository,
)


class PrepSettingsService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.tenant_settings = TenantSettingsRepository(session)
        self.tenant_branding = TenantBrandingRepository(session)
        self.catalog = AppCatalogRepository(session)
        self.tenant_apps = TenantAppRepository(session)
        self.academic_years = TenantAcademicYearRepository(session)
        self.grading_rules = TenantGradingRuleRepository(session)
        self.attendance_rules = TenantAttendanceRuleRepository(session)
        self.integrations = TenantIntegrationRepository(session)
        self.app_settings = TenantAppSettingRepository(session)

    async def get_general_settings(self, context: TenantContext) -> TenantSettings:
        tenant_id = self._require_tenant_id(context)
        settings = await self.tenant_settings.get_for_tenant(tenant_id)
        if settings is None:
            settings = TenantSettings(tenant_id=tenant_id)
            await self.tenant_settings.add(settings)
            await self.session.commit()
            await set_current_tenant_in_session(self.session, tenant_id)
        ensure_tenant_access(settings.tenant_id, context)
        return settings

    async def update_general_settings(
        self,
        context: TenantContext,
        principal: Principal,
        payload: GeneralSettingsUpdate,
    ) -> TenantSettings:
        settings = await self.get_general_settings(context)
        old_value = self._settings_snapshot(settings)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(settings, field, value)
        await self.session.flush()
        await self.session.refresh(settings)
        await self.session.commit()
        await self._publish_audit_event(
            "prepsettings.general.updated",
            context,
            principal,
            entity_type="tenant_settings",
            entity_id=settings.id,
            old_value=old_value,
            new_value=self._settings_snapshot(settings),
        )
        return settings

    async def get_branding(self, context: TenantContext) -> TenantBranding:
        tenant_id = self._require_tenant_id(context)
        branding = await self.tenant_branding.get_for_tenant(tenant_id)
        if branding is None:
            branding = TenantBranding(tenant_id=tenant_id)
            await self.tenant_branding.add(branding)
            await self.session.commit()
            await set_current_tenant_in_session(self.session, tenant_id)
        ensure_tenant_access(branding.tenant_id, context)
        return branding

    async def update_branding(
        self,
        context: TenantContext,
        principal: Principal,
        payload: BrandingSettingsUpdate,
    ) -> TenantBranding:
        branding = await self.get_branding(context)
        old_value = self._branding_snapshot(branding)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(branding, field, value)
        await self.session.flush()
        await self.session.refresh(branding)
        await self.session.commit()
        await self._publish_audit_event(
            "prepsettings.branding.updated",
            context,
            principal,
            entity_type="tenant_branding",
            entity_id=branding.id,
            old_value=old_value,
            new_value=self._branding_snapshot(branding),
        )
        return branding

    async def list_app_settings(self, context: TenantContext) -> list[dict[str, Any]]:
        tenant_id = self._require_tenant_id(context)
        catalog_entries = list(await self.catalog.list_all())
        tenant_apps = {
            app.app_code: app for app in await self.tenant_apps.list_for_tenant(tenant_id)
        }
        app_settings = {
            item.app_code: item for item in await self.app_settings.list_for_tenant(tenant_id)
        }
        app_codes = sorted(
            {item.code for item in catalog_entries} | set(tenant_apps) | set(app_settings)
        )
        catalog_by_code = {item.code: item for item in catalog_entries}
        return [
            self._app_settings_response(
                app_code,
                catalog_by_code.get(app_code),
                tenant_apps.get(app_code),
                app_settings.get(app_code),
            )
            for app_code in app_codes
        ]

    async def toggle_app(
        self,
        context: TenantContext,
        principal: Principal,
        app_code: str,
        payload: AppSettingsToggleRequest,
    ) -> dict[str, Any]:
        tenant_id = self._require_tenant_id(context)
        normalized_app_code = app_code.strip().lower()
        tenant_app = await self.tenant_apps.get_for_tenant(tenant_id, normalized_app_code)
        if tenant_app is None:
            raise PrepSuiteError(
                "app_subscription_required",
                "This app is not subscribed for the tenant.",
                status_code=403,
                details={"app_code": normalized_app_code},
            )
        catalog_app = await self.catalog.get_by_code(normalized_app_code)
        app_setting = await self._get_or_create_app_setting(
            tenant_id,
            normalized_app_code,
            principal.user_id,
        )
        old_value = self._app_toggle_snapshot(tenant_app, app_setting)

        if tenant_app.status == TenantAppStatus.LOCKED.value:
            raise PrepSuiteError(
                "app_locked",
                "Locked apps cannot be toggled by a tenant admin.",
                status_code=403,
                details={"app_code": normalized_app_code},
            )

        if payload.enabled:
            self._assert_subscription_allows_enable(tenant_app, catalog_app)
            tenant_app.status = (
                TenantAppStatus.TRIAL.value
                if tenant_app.subscription_status == SubscriptionStatus.TRIAL.value
                else TenantAppStatus.ENABLED.value
            )
        else:
            tenant_app.status = TenantAppStatus.DISABLED.value

        app_setting.enabled_by_tenant = payload.enabled
        app_setting.updated_by = principal.user_id
        if payload.settings is not None:
            app_setting.settings = payload.settings
        await self.session.flush()
        await self.session.refresh(tenant_app)
        await self.session.refresh(app_setting)
        await self.session.commit()
        await self._publish_audit_event(
            "prepsettings.app_toggled",
            context,
            principal,
            entity_type="tenant_app",
            entity_id=tenant_app.id,
            old_value=old_value,
            new_value=self._app_toggle_snapshot(tenant_app, app_setting),
        )
        return self._app_settings_response(
            normalized_app_code,
            catalog_app,
            tenant_app,
            app_setting,
        )

    async def list_academic_years(self, context: TenantContext) -> list[TenantAcademicYear]:
        tenant_id = self._require_tenant_id(context)
        return list(await self.academic_years.list_for_tenant(tenant_id))

    async def create_academic_year(
        self,
        context: TenantContext,
        principal: Principal,
        payload: AcademicYearCreate,
    ) -> TenantAcademicYear:
        tenant_id = self._require_tenant_id(context)
        if payload.is_current:
            await self.academic_years.clear_current(tenant_id)
        academic_year = TenantAcademicYear(
            tenant_id=tenant_id,
            **payload.model_dump(mode="python"),
        )
        try:
            await self.academic_years.add(academic_year)
            await self.session.flush()
            await self.session.refresh(academic_year)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "academic_year_conflict",
                "Academic year code already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_audit_event(
            "prepsettings.academic_year.created",
            context,
            principal,
            entity_type="tenant_academic_year",
            entity_id=academic_year.id,
            old_value={},
            new_value=self._academic_year_snapshot(academic_year),
        )
        return academic_year

    async def update_academic_year(
        self,
        context: TenantContext,
        principal: Principal,
        academic_year_id: uuid.UUID,
        payload: AcademicYearUpdate,
    ) -> TenantAcademicYear:
        tenant_id = self._require_tenant_id(context)
        academic_year = await self.academic_years.get_for_tenant(tenant_id, academic_year_id)
        if academic_year is None:
            raise PrepSuiteError(
                "academic_year_not_found",
                "Academic year was not found.",
                status_code=404,
            )
        old_value = self._academic_year_snapshot(academic_year)
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        starts_on = update_data.get("starts_on", academic_year.starts_on)
        ends_on = update_data.get("ends_on", academic_year.ends_on)
        if ends_on <= starts_on:
            raise PrepSuiteError(
                "invalid_academic_year_dates",
                "Academic year end date must be after start date.",
                status_code=422,
            )
        if update_data.get("is_current") is True:
            await self.academic_years.clear_current(tenant_id, except_id=academic_year.id)
        for field, value in update_data.items():
            setattr(academic_year, field, value)
        await self.session.flush()
        await self.session.refresh(academic_year)
        await self.session.commit()
        await self._publish_audit_event(
            "prepsettings.academic_year.updated",
            context,
            principal,
            entity_type="tenant_academic_year",
            entity_id=academic_year.id,
            old_value=old_value,
            new_value=self._academic_year_snapshot(academic_year),
        )
        return academic_year

    async def get_grading_rule(self, context: TenantContext) -> TenantGradingRule:
        tenant_id = self._require_tenant_id(context)
        rule = await self.grading_rules.get_default(tenant_id)
        if rule is None:
            rule = TenantGradingRule(
                tenant_id=tenant_id,
                code="default",
                name="Default grading",
                grade_scale={},
                pass_percentage=None,
                rounding_strategy=None,
                status=RuleStatus.ACTIVE.value,
                is_default=True,
            )
            await self.grading_rules.add(rule)
            await self.session.commit()
            await set_current_tenant_in_session(self.session, tenant_id)
        return rule

    async def update_grading_rule(
        self,
        context: TenantContext,
        principal: Principal,
        payload: GradingRuleUpdate,
    ) -> TenantGradingRule:
        rule = await self.get_grading_rule(context)
        old_value = self._grading_snapshot(rule)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
        await self.session.flush()
        await self.session.refresh(rule)
        await self.session.commit()
        await self._publish_audit_event(
            "prepsettings.grading_rules.updated",
            context,
            principal,
            entity_type="tenant_grading_rule",
            entity_id=rule.id,
            old_value=old_value,
            new_value=self._grading_snapshot(rule),
        )
        return rule

    async def get_attendance_rule(self, context: TenantContext) -> TenantAttendanceRule:
        tenant_id = self._require_tenant_id(context)
        rule = await self.attendance_rules.get_default(tenant_id)
        if rule is None:
            rule = TenantAttendanceRule(
                tenant_id=tenant_id,
                code="default",
                name="Default attendance",
                minimum_percentage=None,
                late_threshold_minutes=None,
                absent_after_minutes=None,
                rules={},
                status=RuleStatus.ACTIVE.value,
                is_default=True,
            )
            await self.attendance_rules.add(rule)
            await self.session.commit()
            await set_current_tenant_in_session(self.session, tenant_id)
        return rule

    async def update_attendance_rule(
        self,
        context: TenantContext,
        principal: Principal,
        payload: AttendanceRuleUpdate,
    ) -> TenantAttendanceRule:
        rule = await self.get_attendance_rule(context)
        old_value = self._attendance_snapshot(rule)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
        await self.session.flush()
        await self.session.refresh(rule)
        await self.session.commit()
        await self._publish_audit_event(
            "prepsettings.attendance_rules.updated",
            context,
            principal,
            entity_type="tenant_attendance_rule",
            entity_id=rule.id,
            old_value=old_value,
            new_value=self._attendance_snapshot(rule),
        )
        return rule

    async def _get_or_create_app_setting(
        self,
        tenant_id: uuid.UUID,
        app_code: str,
        actor_user_id: uuid.UUID,
    ) -> TenantAppSetting:
        app_setting = await self.app_settings.get_for_tenant(tenant_id, app_code)
        if app_setting is not None:
            return app_setting
        app_setting = TenantAppSetting(
            tenant_id=tenant_id,
            app_code=app_code,
            enabled_by_tenant=False,
            settings={},
            updated_by=actor_user_id,
        )
        await self.app_settings.add(app_setting)
        return app_setting

    def _assert_subscription_allows_enable(
        self,
        tenant_app: TenantApp,
        catalog_app: AppCatalog | None,
    ) -> None:
        if catalog_app is None or not catalog_app.is_active:
            raise PrepSuiteError(
                "app_not_available",
                "App catalog entry is not active.",
                status_code=403,
                details={"app_code": tenant_app.app_code},
            )
        if tenant_app.subscription_status not in {
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        }:
            raise PrepSuiteError(
                "app_subscription_required",
                "Only active or trial subscriptions can be enabled.",
                status_code=403,
                details={"app_code": tenant_app.app_code},
            )
        if tenant_app.ends_at is not None and tenant_app.ends_at < datetime.now(UTC):
            raise PrepSuiteError(
                "app_subscription_expired",
                "This app subscription has expired.",
                status_code=403,
                details={"app_code": tenant_app.app_code},
            )

    def _app_settings_response(
        self,
        app_code: str,
        catalog_app: AppCatalog | None,
        tenant_app: TenantApp | None,
        app_setting: TenantAppSetting | None,
    ) -> dict[str, Any]:
        enabled_by_tenant = (
            app_setting.enabled_by_tenant
            if app_setting is not None
            else tenant_app is not None
            and tenant_app.status in {TenantAppStatus.ENABLED.value, TenantAppStatus.TRIAL.value}
        )
        return {
            "app_code": app_code,
            "name": catalog_app.name if catalog_app else None,
            "category": catalog_app.category if catalog_app else None,
            "is_core": catalog_app.is_core if catalog_app else False,
            "is_active": catalog_app.is_active if catalog_app else False,
            "tenant_app_status": tenant_app.status if tenant_app else None,
            "subscription_status": tenant_app.subscription_status if tenant_app else None,
            "enabled_by_tenant": bool(enabled_by_tenant),
            "can_enable": self._can_enable(tenant_app, catalog_app),
            "starts_at": tenant_app.starts_at if tenant_app else None,
            "ends_at": tenant_app.ends_at if tenant_app else None,
            "config": tenant_app.config if tenant_app else {},
            "settings": app_setting.settings if app_setting else {},
        }

    def _can_enable(self, tenant_app: TenantApp | None, catalog_app: AppCatalog | None) -> bool:
        if tenant_app is None or catalog_app is None or not catalog_app.is_active:
            return False
        if tenant_app.status == TenantAppStatus.LOCKED.value:
            return False
        if tenant_app.subscription_status not in {
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        }:
            return False
        return tenant_app.ends_at is None or tenant_app.ends_at >= datetime.now(UTC)

    def _require_tenant_id(self, context: TenantContext) -> uuid.UUID:
        if context.tenant_id is None:
            raise PrepSuiteError("tenant_required", "Tenant context is required.", status_code=400)
        return context.tenant_id

    async def _publish_audit_event(
        self,
        event_type: str,
        context: TenantContext,
        principal: Principal,
        *,
        entity_type: str,
        entity_id: uuid.UUID,
        old_value: dict[str, Any],
        new_value: dict[str, Any],
    ) -> None:
        await self.dispatcher.publish(
            DomainEvent(
                event_type=event_type,
                tenant_id=context.tenant_id,
                payload={
                    "actor_user_id": str(principal.user_id),
                    "entity_type": entity_type,
                    "entity_id": str(entity_id),
                    "old_value": old_value,
                    "new_value": new_value,
                },
            )
        )

    def _settings_snapshot(self, settings: TenantSettings) -> dict[str, Any]:
        return {
            "timezone": settings.timezone,
            "locale": settings.locale,
            "general_settings": settings.general_settings,
            "notification_preferences": settings.notification_preferences,
        }

    def _branding_snapshot(self, branding: TenantBranding) -> dict[str, Any]:
        return {
            "logo_url": branding.logo_url,
            "primary_color": branding.primary_color,
            "secondary_color": branding.secondary_color,
            "accent_color": branding.accent_color,
            "branding_settings": branding.branding_settings,
        }

    def _app_toggle_snapshot(
        self,
        tenant_app: TenantApp,
        app_setting: TenantAppSetting,
    ) -> dict[str, Any]:
        return {
            "app_code": tenant_app.app_code,
            "tenant_app_status": tenant_app.status,
            "subscription_status": tenant_app.subscription_status,
            "enabled_by_tenant": app_setting.enabled_by_tenant,
            "settings": app_setting.settings,
        }

    def _academic_year_snapshot(self, academic_year: TenantAcademicYear) -> dict[str, Any]:
        return {
            "name": academic_year.name,
            "code": academic_year.code,
            "starts_on": academic_year.starts_on.isoformat(),
            "ends_on": academic_year.ends_on.isoformat(),
            "status": academic_year.status,
            "is_current": academic_year.is_current,
            "settings": academic_year.settings,
        }

    def _grading_snapshot(self, rule: TenantGradingRule) -> dict[str, Any]:
        return {
            "name": rule.name,
            "grade_scale": rule.grade_scale,
            "pass_percentage": str(rule.pass_percentage) if rule.pass_percentage else None,
            "rounding_strategy": rule.rounding_strategy,
            "status": rule.status,
        }

    def _attendance_snapshot(self, rule: TenantAttendanceRule) -> dict[str, Any]:
        return {
            "name": rule.name,
            "minimum_percentage": str(rule.minimum_percentage)
            if rule.minimum_percentage
            else None,
            "late_threshold_minutes": rule.late_threshold_minutes,
            "absent_after_minutes": rule.absent_after_minutes,
            "rules": rule.rules,
            "status": rule.status,
        }
