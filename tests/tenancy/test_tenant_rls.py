from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tenant_context import set_current_tenant_in_session
from app.modules.tenancy.models import TenantDomain, TenantSettings
from app.modules.tenancy.schemas import TenantCreate
from app.modules.tenancy.service import TenantService


async def create_service_tenant(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    slug: str,
) -> uuid.UUID:
    async with session_factory() as session:
        tenant = await TenantService(session).create_tenant(
            TenantCreate(name=name, slug=slug, status="active", plan_type="starter")
        )
        return tenant.id


async def test_rls_hides_tenant_settings_without_current_tenant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await create_service_tenant(session_factory, name="Tenant A", slug="tenant-a")
    await create_service_tenant(session_factory, name="Tenant B", slug="tenant-b")

    async with session_factory() as session:
        rows = (await session.scalars(select(TenantSettings))).all()

    assert rows == []


async def test_rls_limits_reads_to_current_tenant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a_id = await create_service_tenant(session_factory, name="Tenant A", slug="tenant-a")
    tenant_b_id = await create_service_tenant(session_factory, name="Tenant B", slug="tenant-b")

    async with session_factory() as session:
        await set_current_tenant_in_session(session, tenant_a_id)
        rows = (await session.scalars(select(TenantSettings))).all()

    assert len(rows) == 1
    assert rows[0].tenant_id == tenant_a_id
    assert rows[0].tenant_id != tenant_b_id


async def test_rls_blocks_writes_for_another_tenant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a_id = await create_service_tenant(session_factory, name="Tenant A", slug="tenant-a")
    tenant_b_id = await create_service_tenant(session_factory, name="Tenant B", slug="tenant-b")

    async with session_factory() as session:
        await set_current_tenant_in_session(session, tenant_a_id)
        statement = insert(TenantDomain).values(
            id=uuid.uuid4(),
            tenant_id=tenant_b_id,
            domain="cross-tenant-write.test",
            is_primary=False,
            verification_status="pending",
        )
        with pytest.raises(DBAPIError):
            await session.execute(statement)
            await session.commit()
