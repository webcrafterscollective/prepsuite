from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gates import require_app_enabled
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.students.enums import BatchStatus, StudentStatus
from app.modules.students.schemas import (
    BatchCreate,
    BatchRead,
    BatchStudentAddRequest,
    BatchStudentRead,
    BatchUpdate,
    GuardianCreate,
    StudentBulkImportRequest,
    StudentBulkImportResponse,
    StudentCreate,
    StudentDocumentCreate,
    StudentDocumentRead,
    StudentEnrollmentCreate,
    StudentEnrollmentRead,
    StudentGuardianRead,
    StudentNoteCreate,
    StudentNoteRead,
    StudentPage,
    StudentProfileRead,
    StudentRead,
    StudentTimelineEvent,
    StudentUpdate,
)
from app.modules.students.service import PrepStudentsService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    tags=["PrepStudents"],
    dependencies=[Depends(require_app_enabled("prepstudents"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
StudentStatusQuery = Annotated[StudentStatus | None, Query(alias="status")]
BatchStatusQuery = Annotated[BatchStatus | None, Query(alias="status")]
SearchQuery = Annotated[str | None, Query(max_length=120)]
StudentSortQuery = Annotated[str, Query(pattern="^(created_at|name|admission_no)$")]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.get(
    "/students",
    response_model=StudentPage,
    name="prepstudents:list_students",
    dependencies=[Depends(require_permission("prepstudents.student.read"))],
)
async def list_students(
    context: TenantContextDep,
    session: TenantSessionDep,
    limit: LimitQuery = 50,
    cursor: str | None = None,
    status_filter: StudentStatusQuery = None,
    search: SearchQuery = None,
    batch_id: uuid.UUID | None = None,
    sort: StudentSortQuery = "created_at",
) -> object:
    return await PrepStudentsService(session).list_students(
        context,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        search=search,
        batch_id=batch_id,
        sort=sort,
    )


@router.post(
    "/students",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
    name="prepstudents:create_student",
    dependencies=[Depends(require_permission("prepstudents.student.create"))],
)
async def create_student(
    payload: StudentCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).create_student(context, principal, payload)


@router.post(
    "/students/bulk-import",
    response_model=StudentBulkImportResponse,
    name="prepstudents:bulk_import_students",
    dependencies=[Depends(require_permission("prepstudents.student.import"))],
)
async def bulk_import_students(
    payload: StudentBulkImportRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).bulk_import_students(context, principal, payload)


@router.get(
    "/students/{student_id}",
    response_model=StudentRead,
    name="prepstudents:get_student",
    dependencies=[Depends(require_permission("prepstudents.student.read"))],
)
async def get_student(
    student_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepStudentsService(session).get_student(context, student_id)


@router.patch(
    "/students/{student_id}",
    response_model=StudentRead,
    name="prepstudents:update_student",
    dependencies=[Depends(require_permission("prepstudents.student.update"))],
)
async def update_student(
    student_id: uuid.UUID,
    payload: StudentUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).update_student(
        context,
        principal,
        student_id,
        payload,
    )


@router.delete(
    "/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="prepstudents:delete_student",
    dependencies=[Depends(require_permission("prepstudents.student.delete"))],
)
async def delete_student(
    student_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> Response:
    await PrepStudentsService(session).delete_student(context, principal, student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/students/{student_id}/timeline",
    response_model=list[StudentTimelineEvent],
    name="prepstudents:get_student_timeline",
    dependencies=[Depends(require_permission("prepstudents.student.read"))],
)
async def get_student_timeline(
    student_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepStudentsService(session).timeline(context, student_id)


@router.get(
    "/students/{student_id}/profile",
    response_model=StudentProfileRead,
    name="prepstudents:get_student_profile",
    dependencies=[Depends(require_permission("prepstudents.student.read"))],
)
async def get_student_profile(
    student_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepStudentsService(session).get_profile(context, student_id)


@router.post(
    "/students/{student_id}/guardians",
    response_model=StudentGuardianRead,
    status_code=status.HTTP_201_CREATED,
    name="prepstudents:add_guardian",
    dependencies=[Depends(require_permission("prepstudents.student.update"))],
)
async def add_guardian(
    student_id: uuid.UUID,
    payload: GuardianCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).add_guardian(context, principal, student_id, payload)


@router.post(
    "/students/{student_id}/notes",
    response_model=StudentNoteRead,
    status_code=status.HTTP_201_CREATED,
    name="prepstudents:add_student_note",
    dependencies=[Depends(require_permission("prepstudents.student.update"))],
)
async def add_student_note(
    student_id: uuid.UUID,
    payload: StudentNoteCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).add_note(context, principal, student_id, payload)


@router.post(
    "/students/{student_id}/documents",
    response_model=StudentDocumentRead,
    status_code=status.HTTP_201_CREATED,
    name="prepstudents:add_student_document",
    dependencies=[Depends(require_permission("prepstudents.student.update"))],
)
async def add_student_document(
    student_id: uuid.UUID,
    payload: StudentDocumentCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).add_document(context, principal, student_id, payload)


@router.post(
    "/students/{student_id}/enrollments",
    response_model=StudentEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    name="prepstudents:enroll_student",
    dependencies=[Depends(require_permission("prepstudents.student.update"))],
)
async def enroll_student(
    student_id: uuid.UUID,
    payload: StudentEnrollmentCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).enroll_student(
        context,
        principal,
        student_id,
        payload,
    )


@router.get(
    "/batches",
    response_model=list[BatchRead],
    name="prepstudents:list_batches",
    dependencies=[Depends(require_permission("prepstudents.batch.manage"))],
)
async def list_batches(
    context: TenantContextDep,
    session: TenantSessionDep,
    status_filter: BatchStatusQuery = None,
    search: SearchQuery = None,
) -> object:
    return await PrepStudentsService(session).list_batches(
        context,
        status=status_filter,
        search=search,
    )


@router.post(
    "/batches",
    response_model=BatchRead,
    status_code=status.HTTP_201_CREATED,
    name="prepstudents:create_batch",
    dependencies=[Depends(require_permission("prepstudents.batch.manage"))],
)
async def create_batch(
    payload: BatchCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).create_batch(context, principal, payload)


@router.get(
    "/batches/{batch_id}",
    response_model=BatchRead,
    name="prepstudents:get_batch",
    dependencies=[Depends(require_permission("prepstudents.batch.manage"))],
)
async def get_batch(
    batch_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepStudentsService(session).get_batch(context, batch_id)


@router.patch(
    "/batches/{batch_id}",
    response_model=BatchRead,
    name="prepstudents:update_batch",
    dependencies=[Depends(require_permission("prepstudents.batch.manage"))],
)
async def update_batch(
    batch_id: uuid.UUID,
    payload: BatchUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).update_batch(context, principal, batch_id, payload)


@router.post(
    "/batches/{batch_id}/students",
    response_model=BatchStudentRead,
    status_code=status.HTTP_201_CREATED,
    name="prepstudents:add_student_to_batch",
    dependencies=[Depends(require_permission("prepstudents.batch.manage"))],
)
async def add_student_to_batch(
    batch_id: uuid.UUID,
    payload: BatchStudentAddRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepStudentsService(session).assign_student_to_batch(
        context,
        principal,
        batch_id,
        payload.student_id,
    )


@router.delete(
    "/batches/{batch_id}/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="prepstudents:remove_student_from_batch",
    dependencies=[Depends(require_permission("prepstudents.batch.manage"))],
)
async def remove_student_from_batch(
    batch_id: uuid.UUID,
    student_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> Response:
    await PrepStudentsService(session).remove_student_from_batch(
        context,
        principal,
        batch_id,
        student_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
