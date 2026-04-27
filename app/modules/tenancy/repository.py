from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.tenancy.enums import TenantUserStatus
from app.modules.tenancy.models import (
    AppCatalog,
    Tenant,
    TenantApp,
    TenantBranding,
    TenantDomain,
    TenantSettings,
    TenantUser,
)
from app.shared.repository import Repository


class TenantRepository(Repository[Tenant]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Tenant)

    async def get_active(self, tenant_id: uuid.UUID) -> Tenant | None:
        statement = select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
        return cast(Tenant | None, await self.session.scalar(statement))

    async def get_by_slug(self, slug: str) -> Tenant | None:
        statement = select(Tenant).where(Tenant.slug == slug, Tenant.deleted_at.is_(None))
        return cast(Tenant | None, await self.session.scalar(statement))

    async def get_by_domain(self, domain: str) -> Tenant | None:
        statement = (
            select(Tenant)
            .join(TenantDomain)
            .where(TenantDomain.domain == domain, Tenant.deleted_at.is_(None))
        )
        return cast(Tenant | None, await self.session.scalar(statement))

    async def list(self, limit: int = 100) -> Sequence[Tenant]:
        statement = (
            select(Tenant)
            .where(Tenant.deleted_at.is_(None))
            .order_by(Tenant.created_at.desc())
            .limit(limit)
        )
        return (await self.session.scalars(statement)).all()


class TenantDomainRepository(Repository[TenantDomain]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantDomain)

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantDomain]:
        statement = (
            select(TenantDomain)
            .where(TenantDomain.tenant_id == tenant_id)
            .order_by(TenantDomain.is_primary.desc(), TenantDomain.created_at.asc())
        )
        return (await self.session.scalars(statement)).all()


class AppCatalogRepository(Repository[AppCatalog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AppCatalog)

    async def get_by_code(self, code: str) -> AppCatalog | None:
        statement = select(AppCatalog).where(AppCatalog.code == code)
        return cast(AppCatalog | None, await self.session.scalar(statement))

    async def list_active(self) -> Sequence[AppCatalog]:
        statement = (
            select(AppCatalog).where(AppCatalog.is_active.is_(True)).order_by(AppCatalog.code)
        )
        return (await self.session.scalars(statement)).all()

    async def list_all(self) -> Sequence[AppCatalog]:
        statement = select(AppCatalog).order_by(AppCatalog.code)
        return (await self.session.scalars(statement)).all()


class TenantAppRepository(Repository[TenantApp]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantApp)

    async def get_for_tenant(self, tenant_id: uuid.UUID, app_code: str) -> TenantApp | None:
        statement = select(TenantApp).where(
            TenantApp.tenant_id == tenant_id,
            TenantApp.app_code == app_code,
        )
        return cast(TenantApp | None, await self.session.scalar(statement))

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantApp]:
        statement = (
            select(TenantApp)
            .where(TenantApp.tenant_id == tenant_id)
            .options(selectinload(TenantApp.catalog_app))
            .order_by(TenantApp.app_code)
        )
        return (await self.session.scalars(statement)).all()


class TenantSettingsRepository(Repository[TenantSettings]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantSettings)

    async def get_for_tenant(self, tenant_id: uuid.UUID) -> TenantSettings | None:
        statement = self._base_query().where(TenantSettings.tenant_id == tenant_id)
        return cast(TenantSettings | None, await self.session.scalar(statement))

    def _base_query(self) -> Select[tuple[TenantSettings]]:
        return select(TenantSettings)


class TenantBrandingRepository(Repository[TenantBranding]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantBranding)

    async def get_for_tenant(self, tenant_id: uuid.UUID) -> TenantBranding | None:
        statement = select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
        return cast(TenantBranding | None, await self.session.scalar(statement))


class TenantUserRepository(Repository[TenantUser]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantUser)

    async def get_active_membership(self, user_id: uuid.UUID) -> TenantUser | None:
        statement = (
            select(TenantUser)
            .where(
                TenantUser.user_id == user_id,
                TenantUser.status == TenantUserStatus.ACTIVE.value,
            )
            .order_by(TenantUser.created_at.asc())
        )
        return cast(TenantUser | None, await self.session.scalar(statement))

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantUser]:
        statement = select(TenantUser).where(TenantUser.tenant_id == tenant_id)
        return (await self.session.scalars(statement)).all()
