from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gates import require_app_enabled
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.attend.schemas import (
    AttendanceCorrectionApproveRequest,
    AttendanceCorrectionCreate,
    AttendanceCorrectionRead,
    EmployeeAttendanceRecordRead,
    EmployeeAttendanceSummaryRead,
    EmployeeCheckInRequest,
    EmployeeCheckOutRequest,
    StudentAttendanceRecordRead,
    StudentAttendanceRecordsRequest,
    StudentAttendanceRecordUpdate,
    StudentAttendanceSessionCreate,
    StudentAttendanceSessionRead,
    StudentAttendanceSummaryRead,
)
from app.modules.attend.service import PrepAttendService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    tags=["PrepAttend"],
    dependencies=[Depends(require_app_enabled("prepattend"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.post(
    "/attend/student-sessions",
    response_model=StudentAttendanceSessionRead,
    status_code=status.HTTP_201_CREATED,
    name="prepattend:create_student_attendance_session",
    dependencies=[Depends(require_permission("prepattend.student.manage"))],
)
async def create_student_session(
    payload: StudentAttendanceSessionCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAttendService(session).create_student_session(context, principal, payload)


@router.post(
    "/attend/student-sessions/{session_id}/records",
    response_model=list[StudentAttendanceRecordRead],
    status_code=status.HTTP_201_CREATED,
    name="prepattend:mark_student_attendance_records",
    dependencies=[Depends(require_permission("prepattend.student.manage"))],
)
async def mark_student_records(
    session_id: uuid.UUID,
    payload: StudentAttendanceRecordsRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAttendService(session).mark_student_records(
        context,
        principal,
        session_id,
        payload,
    )


@router.patch(
    "/attend/student-records/{record_id}",
    response_model=StudentAttendanceRecordRead,
    name="prepattend:update_student_attendance_record",
    dependencies=[Depends(require_permission("prepattend.student.manage"))],
)
async def update_student_record(
    record_id: uuid.UUID,
    payload: StudentAttendanceRecordUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAttendService(session).update_student_record(
        context,
        principal,
        record_id,
        payload,
    )


@router.get(
    "/attend/students/summary",
    response_model=StudentAttendanceSummaryRead,
    name="prepattend:get_student_attendance_summary",
    dependencies=[Depends(require_permission("prepattend.attendance.read"))],
)
async def student_summary(
    context: TenantContextDep,
    session: TenantSessionDep,
    start_date: date,
    end_date: date,
    batch_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
) -> object:
    return await PrepAttendService(session).student_summary(
        context,
        start_date=start_date,
        end_date=end_date,
        batch_id=batch_id,
        student_id=student_id,
    )


@router.post(
    "/attend/employees/check-in",
    response_model=EmployeeAttendanceRecordRead,
    status_code=status.HTTP_201_CREATED,
    name="prepattend:employee_check_in",
    dependencies=[Depends(require_permission("prepattend.employee.manage"))],
)
async def employee_check_in(
    payload: EmployeeCheckInRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAttendService(session).employee_check_in(context, principal, payload)


@router.post(
    "/attend/employees/check-out",
    response_model=EmployeeAttendanceRecordRead,
    name="prepattend:employee_check_out",
    dependencies=[Depends(require_permission("prepattend.employee.manage"))],
)
async def employee_check_out(
    payload: EmployeeCheckOutRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAttendService(session).employee_check_out(context, principal, payload)


@router.get(
    "/attend/employees/summary",
    response_model=EmployeeAttendanceSummaryRead,
    name="prepattend:get_employee_attendance_summary",
    dependencies=[Depends(require_permission("prepattend.attendance.read"))],
)
async def employee_summary(
    context: TenantContextDep,
    session: TenantSessionDep,
    start_date: date,
    end_date: date,
    employee_id: uuid.UUID | None = None,
) -> object:
    return await PrepAttendService(session).employee_summary(
        context,
        start_date=start_date,
        end_date=end_date,
        employee_id=employee_id,
    )


@router.post(
    "/attend/correction-requests",
    response_model=AttendanceCorrectionRead,
    status_code=status.HTTP_201_CREATED,
    name="prepattend:create_attendance_correction_request",
    dependencies=[Depends(require_permission("prepattend.correction.manage"))],
)
async def create_correction_request(
    payload: AttendanceCorrectionCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAttendService(session).create_correction_request(context, principal, payload)


@router.post(
    "/attend/correction-requests/{correction_id}/approve",
    response_model=AttendanceCorrectionRead,
    name="prepattend:approve_attendance_correction_request",
    dependencies=[Depends(require_permission("prepattend.correction.manage"))],
)
async def approve_correction_request(
    correction_id: uuid.UUID,
    payload: AttendanceCorrectionApproveRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAttendService(session).approve_correction_request(
        context,
        principal,
        correction_id,
        payload,
    )
