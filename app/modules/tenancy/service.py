from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PrepSuiteError
from app.core.tenant_context import (
    TenantContext,
    TenantSource,
    ensure_tenant_access,
    set_current_tenant_in_session,
)
from app.modules.tenancy.app_catalog import DEFAULT_APP_CATALOG
from app.modules.tenancy.enums import SubscriptionStatus, TenantAppStatus
from app.modules.tenancy.models import (
    AppCatalog,
    Tenant,
    TenantApp,
    TenantBranding,
    TenantDomain,
    TenantSettings,
    TenantUser,
)
from app.modules.tenancy.repository import (
    AppCatalogRepository,
    TenantAppRepository,
    TenantBrandingRepository,
    TenantDomainRepository,
    TenantRepository,
    TenantSettingsRepository,
    TenantUserRepository,
)
from app.modules.tenancy.schemas import (
    AppCatalogCreate,
    TenantAppUpsert,
    TenantBrandingUpdate,
    TenantCreate,
    TenantDomainCreate,
    TenantSettingsUpdate,
    TenantUserCreate,
)


@dataclass(frozen=True)
class TenantResolutionHints:
    tenant_id: uuid.UUID | None = None
    slug: str | None = None
    domain: str | None = None
    subdomain: str | None = None
    user_id: uuid.UUID | None = None


class TenantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tenants = TenantRepository(session)
        self.domains = TenantDomainRepository(session)
        self.catalog = AppCatalogRepository(session)
        self.apps = TenantAppRepository(session)
        self.settings = TenantSettingsRepository(session)
        self.branding = TenantBrandingRepository(session)
        self.users = TenantUserRepository(session)

    async def create_tenant(self, payload: TenantCreate) -> Tenant:
        tenant = Tenant(
            name=payload.name,
            legal_name=payload.legal_name,
            slug=payload.slug,
            status=payload.status.value,
            plan_type=payload.plan_type,
        )
        try:
            await self.tenants.add(tenant)
            await set_current_tenant_in_session(self.session, tenant.id)
            self.session.add(TenantSettings(tenant_id=tenant.id))
            self.session.add(TenantBranding(tenant_id=tenant.id))
            if payload.primary_domain:
                self.session.add(
                    TenantDomain(
                        tenant_id=tenant.id,
                        domain=payload.primary_domain,
                        is_primary=True,
                    )
                )
            await self.session.flush()
            await self.session.refresh(tenant)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "tenant_conflict",
                "Tenant slug or domain already exists.",
                status_code=409,
            ) from exc
        return tenant

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = await self.tenants.get_active(tenant_id)
        if tenant is None:
            raise PrepSuiteError("tenant_not_found", "Tenant was not found.", status_code=404)
        return tenant

    async def resolve_tenant(self, hints: TenantResolutionHints) -> TenantContext:
        if hints.tenant_id is not None:
            tenant = await self.tenants.get_active(hints.tenant_id)
            return self._context_from_tenant(tenant, "header", slug=hints.slug, domain=hints.domain)

        if hints.slug:
            tenant = await self.tenants.get_by_slug(hints.slug)
            return self._context_from_tenant(tenant, "header", slug=hints.slug, domain=hints.domain)

        if hints.domain:
            tenant = await self.tenants.get_by_domain(hints.domain)
            if tenant is not None:
                return self._context_from_tenant(tenant, "subdomain", domain=hints.domain)

        if hints.subdomain:
            tenant = await self.tenants.get_by_slug(hints.subdomain)
            if tenant is not None:
                return self._context_from_tenant(tenant, "subdomain", slug=hints.subdomain)

        if hints.user_id is not None:
            membership = await self.users.get_active_membership(hints.user_id)
            if membership is not None:
                return TenantContext(
                    tenant_id=membership.tenant_id,
                    source="authenticated_user",
                    user_id=hints.user_id,
                )

        return TenantContext(tenant_id=None)

    async def create_domain(
        self,
        tenant_id: uuid.UUID,
        payload: TenantDomainCreate,
    ) -> TenantDomain:
        await self.get_tenant(tenant_id)
        await set_current_tenant_in_session(self.session, tenant_id)
        domain = TenantDomain(
            tenant_id=tenant_id,
            domain=payload.domain,
            is_primary=payload.is_primary,
            verification_status=payload.verification_status.value,
        )
        try:
            await self.domains.add(domain)
            await self.session.flush()
            await self.session.refresh(domain)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "tenant_domain_conflict",
                "Tenant domain already exists.",
                status_code=409,
            ) from exc
        return domain

    async def upsert_app_catalog(self, payload: AppCatalogCreate) -> AppCatalog:
        app = await self.catalog.get_by_code(payload.code)
        if app is None:
            app = AppCatalog(**payload.model_dump(mode="json"))
            await self.catalog.add(app)
        else:
            app.name = payload.name
            app.description = payload.description
            app.category = payload.category
            app.is_core = payload.is_core
            app.is_active = payload.is_active
        await self.session.flush()
        await self.session.refresh(app)
        await self.session.commit()
        return app

    async def seed_default_app_catalog(self) -> list[AppCatalog]:
        seeded: list[AppCatalog] = []
        for item in DEFAULT_APP_CATALOG:
            seeded.append(await self.upsert_app_catalog(AppCatalogCreate.model_validate(item)))
        return seeded

    async def list_app_catalog(self) -> list[AppCatalog]:
        return list(await self.catalog.list_all())

    async def upsert_tenant_app(
        self,
        tenant_id: uuid.UUID,
        app_code: str,
        payload: TenantAppUpsert,
    ) -> TenantApp:
        await self.get_tenant(tenant_id)
        catalog_app = await self.catalog.get_by_code(app_code)
        if catalog_app is None or not catalog_app.is_active:
            raise PrepSuiteError(
                "app_not_found",
                "App catalog entry was not found.",
                status_code=404,
            )

        if payload.ends_at is not None and payload.ends_at < datetime.now(UTC):
            status = TenantAppStatus.DISABLED.value
        else:
            status = payload.status.value

        await set_current_tenant_in_session(self.session, tenant_id)
        tenant_app = await self.apps.get_for_tenant(tenant_id, app_code)
        if tenant_app is None:
            tenant_app = TenantApp(
                tenant_id=tenant_id,
                app_code=app_code,
                status=status,
                subscription_status=payload.subscription_status.value,
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                config=payload.config,
            )
            await self.apps.add(tenant_app)
        else:
            tenant_app.status = status
            tenant_app.subscription_status = payload.subscription_status.value
            tenant_app.starts_at = payload.starts_at
            tenant_app.ends_at = payload.ends_at
            tenant_app.config = payload.config
        await self.session.flush()
        await self.session.refresh(tenant_app)
        await self.session.commit()
        return tenant_app

    async def list_tenant_apps(self, context: TenantContext) -> list[TenantApp]:
        if context.tenant_id is None:
            raise PrepSuiteError("tenant_required", "Tenant context is required.", status_code=400)
        return list(await self.apps.list_for_tenant(context.tenant_id))

    async def is_app_enabled(self, context: TenantContext, app_code: str) -> bool:
        if context.tenant_id is None:
            return False
        tenant_app = await self.apps.get_for_tenant(context.tenant_id, app_code)
        if tenant_app is None:
            return False
        if tenant_app.status not in {TenantAppStatus.ENABLED.value, TenantAppStatus.TRIAL.value}:
            return False
        if tenant_app.subscription_status not in {
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        }:
            return False
        return tenant_app.ends_at is None or tenant_app.ends_at >= datetime.now(UTC)

    async def get_settings(self, context: TenantContext) -> TenantSettings:
        if context.tenant_id is None:
            raise PrepSuiteError("tenant_required", "Tenant context is required.", status_code=400)
        settings = await self.settings.get_for_tenant(context.tenant_id)
        if settings is None:
            raise PrepSuiteError(
                "tenant_settings_not_found",
                "Tenant settings were not found.",
                status_code=404,
            )
        ensure_tenant_access(settings.tenant_id, context)
        return settings

    async def update_settings(
        self,
        context: TenantContext,
        payload: TenantSettingsUpdate,
    ) -> TenantSettings:
        settings = await self.get_settings(context)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)
        await self.session.flush()
        await self.session.refresh(settings)
        await self.session.commit()
        return settings

    async def get_branding(self, context: TenantContext) -> TenantBranding:
        if context.tenant_id is None:
            raise PrepSuiteError("tenant_required", "Tenant context is required.", status_code=400)
        branding = await self.branding.get_for_tenant(context.tenant_id)
        if branding is None:
            raise PrepSuiteError(
                "tenant_branding_not_found",
                "Tenant branding was not found.",
                status_code=404,
            )
        ensure_tenant_access(branding.tenant_id, context)
        return branding

    async def update_branding(
        self,
        context: TenantContext,
        payload: TenantBrandingUpdate,
    ) -> TenantBranding:
        branding = await self.get_branding(context)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(branding, field, value)
        await self.session.flush()
        await self.session.refresh(branding)
        await self.session.commit()
        return branding

    async def add_tenant_user(
        self,
        tenant_id: uuid.UUID,
        payload: TenantUserCreate,
    ) -> TenantUser:
        await self.get_tenant(tenant_id)
        await set_current_tenant_in_session(self.session, tenant_id)
        tenant_user = TenantUser(
            tenant_id=tenant_id,
            user_id=payload.user_id,
            status=payload.status.value,
            is_primary_admin=payload.is_primary_admin,
        )
        try:
            await self.users.add(tenant_user)
            await self.session.flush()
            await self.session.refresh(tenant_user)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "tenant_user_conflict",
                "Tenant user already exists.",
                status_code=409,
            ) from exc
        return tenant_user

    def _context_from_tenant(
        self,
        tenant: Tenant | None,
        source: TenantSource,
        *,
        slug: str | None = None,
        domain: str | None = None,
    ) -> TenantContext:
        if tenant is None:
            return TenantContext(tenant_id=None)
        if source == "subdomain":
            return TenantContext(tenant_id=tenant.id, source="subdomain", slug=slug, domain=domain)
        return TenantContext(tenant_id=tenant.id, source="header", slug=slug, domain=domain)
