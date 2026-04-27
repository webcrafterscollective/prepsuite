from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.settings.schemas import (
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearUpdate,
    AppSettingsRead,
    AppSettingsToggleRequest,
    AttendanceRuleRead,
    AttendanceRuleUpdate,
    BrandingSettingsRead,
    BrandingSettingsUpdate,
    GeneralSettingsRead,
    GeneralSettingsUpdate,
    GradingRuleRead,
    GradingRuleUpdate,
)
from app.modules.settings.service import PrepSettingsService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    prefix="/settings",
    tags=["PrepSettings"],
    dependencies=[Depends(require_permission("prepsettings.settings.manage"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.get("/general", response_model=GeneralSettingsRead, name="prepsettings:get_general")
async def get_general_settings(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepSettingsService(session).get_general_settings(context)


@router.patch(
    "/general",
    response_model=GeneralSettingsRead,
    name="prepsettings:update_general",
)
async def update_general_settings(
    payload: GeneralSettingsUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepSettingsService(session).update_general_settings(context, principal, payload)


@router.get("/branding", response_model=BrandingSettingsRead, name="prepsettings:get_branding")
async def get_branding(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepSettingsService(session).get_branding(context)


@router.patch(
    "/branding",
    response_model=BrandingSettingsRead,
    name="prepsettings:update_branding",
)
async def update_branding(
    payload: BrandingSettingsUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepSettingsService(session).update_branding(context, principal, payload)


@router.get("/apps", response_model=list[AppSettingsRead], name="prepsettings:list_apps")
async def list_apps(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepSettingsService(session).list_app_settings(context)


@router.patch(
    "/apps/{app_code}/toggle",
    response_model=AppSettingsRead,
    name="prepsettings:toggle_app",
)
async def toggle_app(
    app_code: str,
    payload: AppSettingsToggleRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepSettingsService(session).toggle_app(context, principal, app_code, payload)


@router.get(
    "/academic-years",
    response_model=list[AcademicYearRead],
    name="prepsettings:list_academic_years",
)
async def list_academic_years(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepSettingsService(session).list_academic_years(context)


@router.post(
    "/academic-years",
    response_model=AcademicYearRead,
    status_code=status.HTTP_201_CREATED,
    name="prepsettings:create_academic_year",
)
async def create_academic_year(
    payload: AcademicYearCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepSettingsService(session).create_academic_year(context, principal, payload)


@router.patch(
    "/academic-years/{academic_year_id}",
    response_model=AcademicYearRead,
    name="prepsettings:update_academic_year",
)
async def update_academic_year(
    academic_year_id: uuid.UUID,
    payload: AcademicYearUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepSettingsService(session).update_academic_year(
        context,
        principal,
        academic_year_id,
        payload,
    )


@router.get(
    "/grading-rules",
    response_model=GradingRuleRead,
    name="prepsettings:get_grading_rules",
)
async def get_grading_rules(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepSettingsService(session).get_grading_rule(context)


@router.patch(
    "/grading-rules",
    response_model=GradingRuleRead,
    name="prepsettings:update_grading_rules",
)
async def update_grading_rules(
    payload: GradingRuleUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepSettingsService(session).update_grading_rule(context, principal, payload)


@router.get(
    "/attendance-rules",
    response_model=AttendanceRuleRead,
    name="prepsettings:get_attendance_rules",
)
async def get_attendance_rules(
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepSettingsService(session).get_attendance_rule(context)


@router.patch(
    "/attendance-rules",
    response_model=AttendanceRuleRead,
    name="prepsettings:update_attendance_rules",
)
async def update_attendance_rules(
    payload: AttendanceRuleUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepSettingsService(session).update_attendance_rule(context, principal, payload)
