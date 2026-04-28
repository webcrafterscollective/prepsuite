from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gates import require_app_enabled
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.live.enums import LiveClassStatus
from app.modules.live.schemas import (
    LiveAccessValidationRead,
    LiveAccessValidationRequest,
    LiveAttendanceEventsRead,
    LiveAttendanceEventsRequest,
    LiveClassCancelRequest,
    LiveClassCreate,
    LiveClassDetailRead,
    LiveClassPage,
    LiveClassRead,
    LiveClassRecordingCreate,
    LiveClassRecordingRead,
    LiveClassUpdate,
)
from app.modules.live.service import PrepLiveService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    tags=["PrepLive"],
    dependencies=[Depends(require_app_enabled("preplive"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.post(
    "/live/classes",
    response_model=LiveClassRead,
    status_code=status.HTTP_201_CREATED,
    name="preplive:schedule_class",
    dependencies=[Depends(require_permission("preplive.class.schedule"))],
)
async def schedule_class(
    payload: LiveClassCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).schedule_class(context, principal, payload)


@router.get(
    "/live/classes",
    response_model=LiveClassPage,
    name="preplive:list_classes",
    dependencies=[Depends(require_permission("preplive.class.read"))],
)
async def list_classes(
    context: TenantContextDep,
    session: TenantSessionDep,
    limit: LimitQuery = 50,
    cursor: str | None = None,
    status_filter: Annotated[LiveClassStatus | None, Query(alias="status")] = None,
    batch_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
) -> object:
    return await PrepLiveService(session).list_classes(
        context,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        batch_id=batch_id,
        student_id=student_id,
        teacher_id=teacher_id,
        starts_from=starts_from,
        starts_to=starts_to,
    )


@router.get(
    "/live/classes/by-code/{class_code}",
    response_model=LiveClassDetailRead,
    name="preplive:get_class_by_code",
    dependencies=[Depends(require_permission("preplive.class.read"))],
)
async def get_class_by_code(
    class_code: str,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepLiveService(session).get_by_code(context, class_code)


@router.get(
    "/live/classes/{live_class_id}",
    response_model=LiveClassDetailRead,
    name="preplive:get_class",
    dependencies=[Depends(require_permission("preplive.class.read"))],
)
async def get_class(
    live_class_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepLiveService(session).get_class(context, live_class_id)


@router.patch(
    "/live/classes/{live_class_id}",
    response_model=LiveClassRead,
    name="preplive:update_class",
    dependencies=[Depends(require_permission("preplive.class.manage"))],
)
async def update_class(
    live_class_id: uuid.UUID,
    payload: LiveClassUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).update_class(context, principal, live_class_id, payload)


@router.post(
    "/live/classes/{live_class_id}/cancel",
    response_model=LiveClassRead,
    name="preplive:cancel_class",
    dependencies=[Depends(require_permission("preplive.class.manage"))],
)
async def cancel_class(
    live_class_id: uuid.UUID,
    payload: LiveClassCancelRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).cancel_class(context, principal, live_class_id, payload)


@router.post(
    "/live/classes/{live_class_id}/open",
    response_model=LiveClassRead,
    name="preplive:open_class",
    dependencies=[Depends(require_permission("preplive.class.manage"))],
)
async def open_class(
    live_class_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).open_class(context, principal, live_class_id)


@router.post(
    "/live/classes/{live_class_id}/end",
    response_model=LiveClassRead,
    name="preplive:end_class",
    dependencies=[Depends(require_permission("preplive.class.manage"))],
)
async def end_class(
    live_class_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).end_class(context, principal, live_class_id)


@router.post(
    "/live/classes/{class_code}/validate-access",
    response_model=LiveAccessValidationRead,
    name="preplive:validate_access",
    dependencies=[Depends(require_permission("preplive.access.validate"))],
)
async def validate_access(
    class_code: str,
    payload: LiveAccessValidationRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).validate_access(context, principal, class_code, payload)


@router.post(
    "/live/classes/{live_class_id}/attendance-events",
    response_model=LiveAttendanceEventsRead,
    name="preplive:capture_attendance_events",
    dependencies=[Depends(require_permission("preplive.attendance.sync"))],
)
async def capture_attendance_events(
    live_class_id: uuid.UUID,
    payload: LiveAttendanceEventsRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).capture_attendance_events(
        context,
        principal,
        live_class_id,
        payload,
    )


@router.post(
    "/live/classes/{live_class_id}/recordings",
    response_model=LiveClassRecordingRead,
    status_code=status.HTTP_201_CREATED,
    name="preplive:add_recording",
    dependencies=[Depends(require_permission("preplive.recording.manage"))],
)
async def add_recording(
    live_class_id: uuid.UUID,
    payload: LiveClassRecordingCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLiveService(session).add_recording(context, principal, live_class_id, payload)
