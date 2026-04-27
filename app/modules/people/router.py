from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gates import require_app_enabled
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.people.enums import DepartmentStatus, EmployeeStatus, EmployeeType
from app.modules.people.schemas import (
    DepartmentCreate,
    DepartmentRead,
    EmployeeCreate,
    EmployeeDocumentCreate,
    EmployeeDocumentRead,
    EmployeeNoteCreate,
    EmployeeNoteRead,
    EmployeePage,
    EmployeeProfileAggregateRead,
    EmployeeRead,
    EmployeeTimelineEvent,
    EmployeeUpdate,
    TeacherAssignmentCreate,
    TeacherAssignmentRead,
    TeacherWorkloadRead,
)
from app.modules.people.service import PrepPeopleService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    tags=["PrepPeople"],
    dependencies=[Depends(require_app_enabled("preppeople"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
EmployeeStatusQuery = Annotated[EmployeeStatus | None, Query(alias="status")]
EmployeeTypeQuery = Annotated[EmployeeType | None, Query(alias="employee_type")]
DepartmentStatusQuery = Annotated[DepartmentStatus | None, Query(alias="status")]
SearchQuery = Annotated[str | None, Query(max_length=120)]
EmployeeSortQuery = Annotated[str, Query(pattern="^(created_at|name|employee_code)$")]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.get(
    "/people/employees",
    response_model=EmployeePage,
    name="preppeople:list_employees",
    dependencies=[Depends(require_permission("preppeople.employee.read"))],
)
async def list_employees(
    context: TenantContextDep,
    session: TenantSessionDep,
    limit: LimitQuery = 50,
    cursor: str | None = None,
    status_filter: EmployeeStatusQuery = None,
    employee_type: EmployeeTypeQuery = None,
    department_id: uuid.UUID | None = None,
    search: SearchQuery = None,
    sort: EmployeeSortQuery = "created_at",
) -> object:
    return await PrepPeopleService(session).list_employees(
        context,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        employee_type=employee_type,
        department_id=department_id,
        search=search,
        sort=sort,
    )


@router.post(
    "/people/employees",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
    name="preppeople:create_employee",
    dependencies=[Depends(require_permission("preppeople.employee.create"))],
)
async def create_employee(
    payload: EmployeeCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepPeopleService(session).create_employee(context, principal, payload)


@router.get(
    "/people/employees/{employee_id}",
    response_model=EmployeeRead,
    name="preppeople:get_employee",
    dependencies=[Depends(require_permission("preppeople.employee.read"))],
)
async def get_employee(
    employee_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepPeopleService(session).get_employee(context, employee_id)


@router.patch(
    "/people/employees/{employee_id}",
    response_model=EmployeeRead,
    name="preppeople:update_employee",
    dependencies=[Depends(require_permission("preppeople.employee.update"))],
)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepPeopleService(session).update_employee(
        context,
        principal,
        employee_id,
        payload,
    )


@router.get(
    "/people/employees/{employee_id}/profile",
    response_model=EmployeeProfileAggregateRead,
    name="preppeople:get_employee_profile",
    dependencies=[Depends(require_permission("preppeople.employee.read"))],
)
async def get_employee_profile(
    employee_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepPeopleService(session).get_profile(context, employee_id)


@router.get(
    "/people/employees/{employee_id}/timeline",
    response_model=list[EmployeeTimelineEvent],
    name="preppeople:get_employee_timeline",
    dependencies=[Depends(require_permission("preppeople.employee.read"))],
)
async def get_employee_timeline(
    employee_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepPeopleService(session).timeline(context, employee_id)


@router.post(
    "/people/employees/{employee_id}/notes",
    response_model=EmployeeNoteRead,
    status_code=status.HTTP_201_CREATED,
    name="preppeople:add_employee_note",
    dependencies=[Depends(require_permission("preppeople.employee.update"))],
)
async def add_employee_note(
    employee_id: uuid.UUID,
    payload: EmployeeNoteCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepPeopleService(session).add_note(context, principal, employee_id, payload)


@router.post(
    "/people/employees/{employee_id}/documents",
    response_model=EmployeeDocumentRead,
    status_code=status.HTTP_201_CREATED,
    name="preppeople:add_employee_document",
    dependencies=[Depends(require_permission("preppeople.employee.update"))],
)
async def add_employee_document(
    employee_id: uuid.UUID,
    payload: EmployeeDocumentCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepPeopleService(session).add_document(context, principal, employee_id, payload)


@router.get(
    "/people/departments",
    response_model=list[DepartmentRead],
    name="preppeople:list_departments",
    dependencies=[Depends(require_permission("preppeople.employee.read"))],
)
async def list_departments(
    context: TenantContextDep,
    session: TenantSessionDep,
    status_filter: DepartmentStatusQuery = None,
    search: SearchQuery = None,
) -> object:
    return await PrepPeopleService(session).list_departments(
        context,
        status=status_filter,
        search=search,
    )


@router.post(
    "/people/departments",
    response_model=DepartmentRead,
    status_code=status.HTTP_201_CREATED,
    name="preppeople:create_department",
    dependencies=[Depends(require_permission("preppeople.department.manage"))],
)
async def create_department(
    payload: DepartmentCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepPeopleService(session).create_department(context, principal, payload)


@router.post(
    "/people/teacher-assignments",
    response_model=TeacherAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    name="preppeople:create_teacher_assignment",
    dependencies=[Depends(require_permission("preppeople.teacher_assignment.manage"))],
)
async def create_teacher_assignment(
    payload: TeacherAssignmentCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepPeopleService(session).create_teacher_assignment(context, principal, payload)


@router.get(
    "/people/teachers/{teacher_id}/workload",
    response_model=TeacherWorkloadRead,
    name="preppeople:get_teacher_workload",
    dependencies=[Depends(require_permission("preppeople.employee.read"))],
)
async def get_teacher_workload(
    teacher_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepPeopleService(session).teacher_workload(context, teacher_id)
