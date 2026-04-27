from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.people.enums import TeacherAssignmentStatus
from app.modules.people.models import (
    Department,
    Employee,
    EmployeeDocument,
    EmployeeNote,
    EmployeeProfile,
    EmployeeStatusHistory,
    TeacherAssignment,
)
from app.shared.repository import Repository


@dataclass(frozen=True)
class CursorResult[T]:
    items: list[T]
    next_cursor: str | None
    has_more: bool


def encode_cursor(created_at: datetime, entity_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{entity_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    created_at, entity_id = raw.split("|", maxsplit=1)
    return datetime.fromisoformat(created_at), uuid.UUID(entity_id)


class DepartmentRepository(Repository[Department]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Department)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> Department | None:
        statement = select(Department).where(
            Department.tenant_id == tenant_id,
            Department.id == department_id,
            Department.deleted_at.is_(None),
        )
        return cast(Department | None, await self.session.scalar(statement))

    async def get_by_code(self, tenant_id: uuid.UUID, code: str) -> Department | None:
        statement = select(Department).where(
            Department.tenant_id == tenant_id,
            Department.code == code,
            Department.deleted_at.is_(None),
        )
        return cast(Department | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        status: str | None,
        search: str | None,
    ) -> Sequence[Department]:
        statement = select(Department).where(
            Department.tenant_id == tenant_id,
            Department.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(Department.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(Department.name.ilike(pattern), Department.code.ilike(pattern))
            )
        statement = statement.order_by(Department.name.asc(), Department.id.desc())
        return (await self.session.scalars(statement)).all()


class EmployeeRepository(Repository[Employee]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Employee)

    async def get_for_tenant(self, tenant_id: uuid.UUID, employee_id: uuid.UUID) -> Employee | None:
        statement = (
            self._base_query()
            .where(
                Employee.tenant_id == tenant_id,
                Employee.id == employee_id,
                Employee.deleted_at.is_(None),
            )
            .options(selectinload(Employee.department), selectinload(Employee.profile))
        )
        return cast(Employee | None, await self.session.scalar(statement))

    async def get_by_code(self, tenant_id: uuid.UUID, employee_code: str) -> Employee | None:
        statement = self._base_query().where(
            Employee.tenant_id == tenant_id,
            Employee.employee_code == employee_code,
            Employee.deleted_at.is_(None),
        )
        return cast(Employee | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
        employee_type: str | None,
        department_id: uuid.UUID | None,
        search: str | None,
        sort: str,
    ) -> CursorResult[Employee]:
        statement = self._base_query().where(
            Employee.tenant_id == tenant_id,
            Employee.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(Employee.status == status)
        if employee_type is not None:
            statement = statement.where(Employee.employee_type == employee_type)
        if department_id is not None:
            statement = statement.where(Employee.department_id == department_id)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Employee.first_name.ilike(pattern),
                    Employee.last_name.ilike(pattern),
                    Employee.employee_code.ilike(pattern),
                    Employee.email.ilike(pattern),
                    Employee.phone.ilike(pattern),
                )
            )
        if cursor:
            created_at, entity_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    Employee.created_at < created_at,
                    and_(Employee.created_at == created_at, Employee.id < entity_id),
                )
            )
        statement = self._apply_sort(statement, sort).limit(limit + 1)
        rows = list((await self.session.scalars(statement)).all())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
        )
        return CursorResult(items=items, next_cursor=next_cursor, has_more=has_more)

    async def profile(self, tenant_id: uuid.UUID, employee_id: uuid.UUID) -> Employee | None:
        statement = (
            select(Employee)
            .where(
                Employee.tenant_id == tenant_id,
                Employee.id == employee_id,
                Employee.deleted_at.is_(None),
            )
            .options(
                selectinload(Employee.department),
                selectinload(Employee.profile),
                selectinload(Employee.documents),
                selectinload(Employee.notes),
                selectinload(Employee.status_history),
                selectinload(Employee.assignments),
            )
        )
        return cast(Employee | None, await self.session.scalar(statement))

    def _base_query(self) -> Select[tuple[Employee]]:
        return select(Employee)

    def _apply_sort(self, statement: Select[tuple[Employee]], sort: str) -> Select[tuple[Employee]]:
        if sort == "name":
            return statement.order_by(
                Employee.first_name.asc(),
                Employee.last_name.asc(),
                Employee.id.desc(),
            )
        if sort == "employee_code":
            return statement.order_by(Employee.employee_code.asc(), Employee.id.desc())
        return statement.order_by(Employee.created_at.desc(), Employee.id.desc())


class EmployeeProfileRepository(Repository[EmployeeProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmployeeProfile)

    async def get_by_employee(
        self,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> EmployeeProfile | None:
        statement = select(EmployeeProfile).where(
            EmployeeProfile.tenant_id == tenant_id,
            EmployeeProfile.employee_id == employee_id,
        )
        return cast(EmployeeProfile | None, await self.session.scalar(statement))


class EmployeeDocumentRepository(Repository[EmployeeDocument]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmployeeDocument)


class EmployeeNoteRepository(Repository[EmployeeNote]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmployeeNote)


class EmployeeStatusHistoryRepository(Repository[EmployeeStatusHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmployeeStatusHistory)


class TeacherAssignmentRepository(Repository[TeacherAssignment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TeacherAssignment)

    async def list_for_teacher(
        self,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> Sequence[TeacherAssignment]:
        statement = (
            select(TeacherAssignment)
            .where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.teacher_id == teacher_id,
            )
            .order_by(TeacherAssignment.created_at.desc(), TeacherAssignment.id.desc())
        )
        return (await self.session.scalars(statement)).all()

    async def active_count(self, tenant_id: uuid.UUID, teacher_id: uuid.UUID) -> int:
        statement = select(func.count(TeacherAssignment.id)).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.status == TeacherAssignmentStatus.ACTIVE.value,
        )
        return int(await self.session.scalar(statement) or 0)
