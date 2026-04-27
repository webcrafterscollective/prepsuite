from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import (
    TenantAcademicYear,
    TenantAppSetting,
    TenantAttendanceRule,
    TenantGradingRule,
    TenantIntegration,
)
from app.shared.repository import Repository


class TenantAcademicYearRepository(Repository[TenantAcademicYear]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantAcademicYear)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> TenantAcademicYear | None:
        statement = select(TenantAcademicYear).where(
            TenantAcademicYear.tenant_id == tenant_id,
            TenantAcademicYear.id == academic_year_id,
            TenantAcademicYear.deleted_at.is_(None),
        )
        return cast(TenantAcademicYear | None, await self.session.scalar(statement))

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantAcademicYear]:
        statement = (
            select(TenantAcademicYear)
            .where(
                TenantAcademicYear.tenant_id == tenant_id,
                TenantAcademicYear.deleted_at.is_(None),
            )
            .order_by(
                TenantAcademicYear.is_current.desc(),
                TenantAcademicYear.starts_on.desc(),
                TenantAcademicYear.name,
            )
        )
        return (await self.session.scalars(statement)).all()

    async def clear_current(self, tenant_id: uuid.UUID, except_id: uuid.UUID | None = None) -> None:
        statement = update(TenantAcademicYear).where(
            TenantAcademicYear.tenant_id == tenant_id,
            TenantAcademicYear.is_current.is_(True),
            TenantAcademicYear.deleted_at.is_(None),
        )
        if except_id is not None:
            statement = statement.where(TenantAcademicYear.id != except_id)
        await self.session.execute(statement.values(is_current=False))


class TenantGradingRuleRepository(Repository[TenantGradingRule]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantGradingRule)

    async def get_default(self, tenant_id: uuid.UUID) -> TenantGradingRule | None:
        statement = select(TenantGradingRule).where(
            TenantGradingRule.tenant_id == tenant_id,
            TenantGradingRule.is_default.is_(True),
            TenantGradingRule.deleted_at.is_(None),
        )
        return cast(TenantGradingRule | None, await self.session.scalar(statement))


class TenantAttendanceRuleRepository(Repository[TenantAttendanceRule]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantAttendanceRule)

    async def get_default(self, tenant_id: uuid.UUID) -> TenantAttendanceRule | None:
        statement = select(TenantAttendanceRule).where(
            TenantAttendanceRule.tenant_id == tenant_id,
            TenantAttendanceRule.is_default.is_(True),
            TenantAttendanceRule.deleted_at.is_(None),
        )
        return cast(TenantAttendanceRule | None, await self.session.scalar(statement))


class TenantIntegrationRepository(Repository[TenantIntegration]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantIntegration)

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantIntegration]:
        statement = (
            select(TenantIntegration)
            .where(TenantIntegration.tenant_id == tenant_id, TenantIntegration.deleted_at.is_(None))
            .order_by(TenantIntegration.integration_type, TenantIntegration.provider)
        )
        return (await self.session.scalars(statement)).all()


class TenantAppSettingRepository(Repository[TenantAppSetting]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantAppSetting)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        app_code: str,
    ) -> TenantAppSetting | None:
        statement = select(TenantAppSetting).where(
            TenantAppSetting.tenant_id == tenant_id,
            TenantAppSetting.app_code == app_code,
        )
        return cast(TenantAppSetting | None, await self.session.scalar(statement))

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantAppSetting]:
        statement = (
            select(TenantAppSetting)
            .where(TenantAppSetting.tenant_id == tenant_id)
            .order_by(TenantAppSetting.app_code)
        )
        return (await self.session.scalars(statement)).all()
