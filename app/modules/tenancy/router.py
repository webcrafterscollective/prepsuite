from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.tenant_context import TenantContext
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context
from app.modules.tenancy.schemas import (
    AppCatalogCreate,
    AppCatalogRead,
    TenantAppRead,
    TenantAppUpsert,
    TenantBrandingRead,
    TenantBrandingUpdate,
    TenantContextRead,
    TenantCreate,
    TenantDomainCreate,
    TenantDomainRead,
    TenantRead,
    TenantSettingsRead,
    TenantSettingsUpdate,
    TenantUserCreate,
    TenantUserRead,
)
from app.modules.tenancy.service import TenantService

platform_router = APIRouter(prefix="/platform", tags=["Platform Tenancy"])
tenant_router = APIRouter(prefix="/tenant", tags=["Tenant Context"])
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]


@platform_router.post(
    "/tenants",
    response_model=TenantRead,
    status_code=status.HTTP_201_CREATED,
    name="platform:create_tenant",
)
async def create_tenant(
    payload: TenantCreate,
    session: DbSessionDep,
) -> object:
    return await TenantService(session).create_tenant(payload)


@platform_router.get(
    "/tenants/{tenant_id}",
    response_model=TenantRead,
    name="platform:get_tenant",
)
async def get_tenant(
    tenant_id: uuid.UUID,
    session: DbSessionDep,
) -> object:
    return await TenantService(session).get_tenant(tenant_id)


@platform_router.post(
    "/tenants/{tenant_id}/domains",
    response_model=TenantDomainRead,
    status_code=status.HTTP_201_CREATED,
    name="platform:create_tenant_domain",
)
async def create_tenant_domain(
    tenant_id: uuid.UUID,
    payload: TenantDomainCreate,
    session: DbSessionDep,
) -> object:
    return await TenantService(session).create_domain(tenant_id, payload)


@platform_router.get(
    "/app-catalog",
    response_model=list[AppCatalogRead],
    name="platform:list_app_catalog",
)
async def list_app_catalog(session: DbSessionDep) -> object:
    return await TenantService(session).list_app_catalog()


@platform_router.post(
    "/app-catalog",
    response_model=AppCatalogRead,
    status_code=status.HTTP_201_CREATED,
    name="platform:upsert_app_catalog",
)
async def upsert_app_catalog(
    payload: AppCatalogCreate,
    session: DbSessionDep,
) -> object:
    return await TenantService(session).upsert_app_catalog(payload)


@platform_router.post(
    "/app-catalog/seed",
    response_model=list[AppCatalogRead],
    name="platform:seed_app_catalog",
)
async def seed_app_catalog(session: DbSessionDep) -> object:
    return await TenantService(session).seed_default_app_catalog()


@platform_router.put(
    "/tenants/{tenant_id}/apps/{app_code}",
    response_model=TenantAppRead,
    name="platform:upsert_tenant_app",
)
async def upsert_tenant_app(
    tenant_id: uuid.UUID,
    app_code: str,
    payload: TenantAppUpsert,
    session: DbSessionDep,
) -> object:
    return await TenantService(session).upsert_tenant_app(tenant_id, app_code.lower(), payload)


@platform_router.post(
    "/tenants/{tenant_id}/users",
    response_model=TenantUserRead,
    status_code=status.HTTP_201_CREATED,
    name="platform:add_tenant_user",
)
async def add_tenant_user(
    tenant_id: uuid.UUID,
    payload: TenantUserCreate,
    session: DbSessionDep,
) -> object:
    return await TenantService(session).add_tenant_user(tenant_id, payload)


@tenant_router.get(
    "/current",
    response_model=TenantContextRead,
    name="tenant:get_current_context",
)
async def get_current_tenant(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    tenant_id = context.tenant_id
    if tenant_id is None:
        raise AssertionError("Tenant context dependency returned an unresolved tenant.")
    tenant = await TenantService(session).get_tenant(tenant_id)
    return {"tenant_id": tenant_id, "source": context.source, "tenant": tenant}


@tenant_router.get("/apps", response_model=list[TenantAppRead], name="tenant:list_apps")
async def list_current_tenant_apps(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await TenantService(session).list_tenant_apps(context)


@tenant_router.get(
    "/settings",
    response_model=TenantSettingsRead,
    name="tenant:get_settings",
)
async def get_tenant_settings(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await TenantService(session).get_settings(context)


@tenant_router.patch(
    "/settings",
    response_model=TenantSettingsRead,
    name="tenant:update_settings",
)
async def update_tenant_settings(
    payload: TenantSettingsUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await TenantService(session).update_settings(context, payload)


@tenant_router.get(
    "/branding",
    response_model=TenantBrandingRead,
    name="tenant:get_branding",
)
async def get_tenant_branding(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await TenantService(session).get_branding(context)


@tenant_router.patch(
    "/branding",
    response_model=TenantBrandingRead,
    name="tenant:update_branding",
)
async def update_tenant_branding(
    payload: TenantBrandingUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await TenantService(session).update_branding(context, payload)
