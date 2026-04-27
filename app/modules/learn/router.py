from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gates import require_app_enabled
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.learn.enums import CourseStatus
from app.modules.learn.schemas import (
    CourseAssignBatchRequest,
    CourseAssignTeacherRequest,
    CourseBatchRead,
    CourseCreate,
    CourseDetailRead,
    CourseOutlineRead,
    CoursePage,
    CoursePublishRequest,
    CourseRead,
    CourseReorderRequest,
    CourseTeacherRead,
    CourseUpdate,
    LessonCreate,
    LessonRead,
    LessonUpdate,
    ModuleCreate,
    ModuleRead,
    ModuleUpdate,
)
from app.modules.learn.service import PrepLearnService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    prefix="/learn",
    tags=["PrepLearn"],
    dependencies=[Depends(require_app_enabled("preplearn"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
CourseStatusQuery = Annotated[CourseStatus | None, Query(alias="status")]
SearchQuery = Annotated[str | None, Query(max_length=120)]
CourseSortQuery = Annotated[str, Query(pattern="^(created_at|title|slug)$")]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.get(
    "/courses",
    response_model=CoursePage,
    name="preplearn:list_courses",
    dependencies=[Depends(require_permission("preplearn.course.read"))],
)
async def list_courses(
    context: TenantContextDep,
    session: TenantSessionDep,
    limit: LimitQuery = 50,
    cursor: str | None = None,
    status_filter: CourseStatusQuery = None,
    search: SearchQuery = None,
    sort: CourseSortQuery = "created_at",
) -> object:
    return await PrepLearnService(session).list_courses(
        context,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        search=search,
        sort=sort,
    )


@router.post(
    "/courses",
    response_model=CourseRead,
    status_code=status.HTTP_201_CREATED,
    name="preplearn:create_course",
    dependencies=[Depends(require_permission("preplearn.course.create"))],
)
async def create_course(
    payload: CourseCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).create_course(context, principal, payload)


@router.get(
    "/courses/{course_id}",
    response_model=CourseDetailRead,
    name="preplearn:get_course",
    dependencies=[Depends(require_permission("preplearn.course.read"))],
)
async def get_course(
    course_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepLearnService(session).get_detail(context, course_id)


@router.patch(
    "/courses/{course_id}",
    response_model=CourseRead,
    name="preplearn:update_course",
    dependencies=[Depends(require_permission("preplearn.course.update"))],
)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).update_course(context, principal, course_id, payload)


@router.delete(
    "/courses/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="preplearn:delete_course",
    dependencies=[Depends(require_permission("preplearn.course.delete"))],
)
async def delete_course(
    course_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> Response:
    await PrepLearnService(session).delete_course(context, principal, course_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/courses/{course_id}/publish",
    response_model=CourseDetailRead,
    name="preplearn:publish_course",
    dependencies=[Depends(require_permission("preplearn.course.publish"))],
)
async def publish_course(
    course_id: uuid.UUID,
    payload: CoursePublishRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).publish_course(context, principal, course_id, payload)


@router.post(
    "/courses/{course_id}/archive",
    response_model=CourseRead,
    name="preplearn:archive_course",
    dependencies=[Depends(require_permission("preplearn.course.update"))],
)
async def archive_course(
    course_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).archive_course(context, principal, course_id)


@router.post(
    "/courses/{course_id}/modules",
    response_model=ModuleRead,
    status_code=status.HTTP_201_CREATED,
    name="preplearn:create_module",
    dependencies=[Depends(require_permission("preplearn.course.update"))],
)
async def create_module(
    course_id: uuid.UUID,
    payload: ModuleCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).create_module(context, principal, course_id, payload)


@router.patch(
    "/modules/{module_id}",
    response_model=ModuleRead,
    name="preplearn:update_module",
    dependencies=[Depends(require_permission("preplearn.course.update"))],
)
async def update_module(
    module_id: uuid.UUID,
    payload: ModuleUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).update_module(context, principal, module_id, payload)


@router.post(
    "/modules/{module_id}/lessons",
    response_model=LessonRead,
    status_code=status.HTTP_201_CREATED,
    name="preplearn:create_lesson",
    dependencies=[Depends(require_permission("preplearn.course.update"))],
)
async def create_lesson(
    module_id: uuid.UUID,
    payload: LessonCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).create_lesson(context, principal, module_id, payload)


@router.patch(
    "/lessons/{lesson_id}",
    response_model=LessonRead,
    name="preplearn:update_lesson",
    dependencies=[Depends(require_permission("preplearn.course.update"))],
)
async def update_lesson(
    lesson_id: uuid.UUID,
    payload: LessonUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).update_lesson(context, principal, lesson_id, payload)


@router.post(
    "/courses/{course_id}/reorder",
    response_model=CourseDetailRead,
    name="preplearn:reorder_course",
    dependencies=[Depends(require_permission("preplearn.course.update"))],
)
async def reorder_course(
    course_id: uuid.UUID,
    payload: CourseReorderRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).reorder_course(context, principal, course_id, payload)


@router.post(
    "/courses/{course_id}/assign-batch",
    response_model=CourseBatchRead,
    status_code=status.HTTP_201_CREATED,
    name="preplearn:assign_batch",
    dependencies=[Depends(require_permission("preplearn.course.assign"))],
)
async def assign_batch(
    course_id: uuid.UUID,
    payload: CourseAssignBatchRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).assign_batch(context, principal, course_id, payload)


@router.post(
    "/courses/{course_id}/assign-teacher",
    response_model=CourseTeacherRead,
    status_code=status.HTTP_201_CREATED,
    name="preplearn:assign_teacher",
    dependencies=[Depends(require_permission("preplearn.course.assign"))],
)
async def assign_teacher(
    course_id: uuid.UUID,
    payload: CourseAssignTeacherRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepLearnService(session).assign_teacher(context, principal, course_id, payload)


@router.get(
    "/courses/{course_id}/outline",
    response_model=CourseOutlineRead,
    name="preplearn:get_course_outline",
    dependencies=[Depends(require_permission("preplearn.course.read"))],
)
async def get_course_outline(
    course_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepLearnService(session).get_outline(context, course_id)
