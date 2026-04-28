from __future__ import annotations

import uuid
from datetime import date
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.attend.models import (
    AttendanceCorrectionRequest,
    AttendancePolicy,
    EmployeeAttendanceRecord,
    StudentAttendanceRecord,
    StudentAttendanceSession,
)
from app.shared.repository import Repository


class StudentAttendanceSessionRepository(Repository[StudentAttendanceSession]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentAttendanceSession)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> StudentAttendanceSession | None:
        statement = (
            select(StudentAttendanceSession)
            .where(
                StudentAttendanceSession.tenant_id == tenant_id,
                StudentAttendanceSession.id == session_id,
            )
            .options(selectinload(StudentAttendanceSession.records))
        )
        return cast(StudentAttendanceSession | None, await self.session.scalar(statement))


class StudentAttendanceRecordRepository(Repository[StudentAttendanceRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentAttendanceRecord)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> StudentAttendanceRecord | None:
        statement = select(StudentAttendanceRecord).where(
            StudentAttendanceRecord.tenant_id == tenant_id,
            StudentAttendanceRecord.id == record_id,
        )
        return cast(StudentAttendanceRecord | None, await self.session.scalar(statement))

    async def get_for_session_student(
        self,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> StudentAttendanceRecord | None:
        statement = select(StudentAttendanceRecord).where(
            StudentAttendanceRecord.tenant_id == tenant_id,
            StudentAttendanceRecord.session_id == session_id,
            StudentAttendanceRecord.student_id == student_id,
        )
        return cast(StudentAttendanceRecord | None, await self.session.scalar(statement))

    async def list_for_summary(
        self,
        tenant_id: uuid.UUID,
        *,
        start_date: date,
        end_date: date,
        batch_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
    ) -> list[StudentAttendanceRecord]:
        statement = (
            select(StudentAttendanceRecord)
            .join(
                StudentAttendanceSession,
                StudentAttendanceSession.id == StudentAttendanceRecord.session_id,
            )
            .where(
                StudentAttendanceRecord.tenant_id == tenant_id,
                StudentAttendanceSession.date >= start_date,
                StudentAttendanceSession.date <= end_date,
            )
            .order_by(
                StudentAttendanceRecord.student_id.asc(),
                StudentAttendanceRecord.created_at.asc(),
            )
        )
        if batch_id is not None:
            statement = statement.where(StudentAttendanceSession.batch_id == batch_id)
        if student_id is not None:
            statement = statement.where(StudentAttendanceRecord.student_id == student_id)
        return list((await self.session.scalars(statement)).all())


class EmployeeAttendanceRecordRepository(Repository[EmployeeAttendanceRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmployeeAttendanceRecord)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> EmployeeAttendanceRecord | None:
        statement = select(EmployeeAttendanceRecord).where(
            EmployeeAttendanceRecord.tenant_id == tenant_id,
            EmployeeAttendanceRecord.id == record_id,
        )
        return cast(EmployeeAttendanceRecord | None, await self.session.scalar(statement))

    async def get_for_employee_date(
        self,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
    ) -> EmployeeAttendanceRecord | None:
        statement = select(EmployeeAttendanceRecord).where(
            EmployeeAttendanceRecord.tenant_id == tenant_id,
            EmployeeAttendanceRecord.employee_id == employee_id,
            EmployeeAttendanceRecord.date == attendance_date,
        )
        return cast(EmployeeAttendanceRecord | None, await self.session.scalar(statement))

    async def list_for_summary(
        self,
        tenant_id: uuid.UUID,
        *,
        start_date: date,
        end_date: date,
        employee_id: uuid.UUID | None,
    ) -> list[EmployeeAttendanceRecord]:
        statement = (
            select(EmployeeAttendanceRecord)
            .where(
                EmployeeAttendanceRecord.tenant_id == tenant_id,
                EmployeeAttendanceRecord.date >= start_date,
                EmployeeAttendanceRecord.date <= end_date,
            )
            .order_by(
                EmployeeAttendanceRecord.employee_id.asc(),
                EmployeeAttendanceRecord.date.asc(),
            )
        )
        if employee_id is not None:
            statement = statement.where(EmployeeAttendanceRecord.employee_id == employee_id)
        return list((await self.session.scalars(statement)).all())


class AttendanceCorrectionRequestRepository(Repository[AttendanceCorrectionRequest]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AttendanceCorrectionRequest)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        correction_id: uuid.UUID,
    ) -> AttendanceCorrectionRequest | None:
        statement = select(AttendanceCorrectionRequest).where(
            AttendanceCorrectionRequest.tenant_id == tenant_id,
            AttendanceCorrectionRequest.id == correction_id,
        )
        return cast(AttendanceCorrectionRequest | None, await self.session.scalar(statement))


class AttendancePolicyRepository(Repository[AttendancePolicy]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AttendancePolicy)
