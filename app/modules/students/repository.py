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

from app.modules.students.enums import BatchStudentStatus
from app.modules.students.models import (
    Batch,
    BatchStudent,
    Guardian,
    Student,
    StudentDocument,
    StudentEnrollment,
    StudentGuardian,
    StudentNote,
    StudentStatusHistory,
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


class StudentRepository(Repository[Student]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Student)

    async def get_for_tenant(self, tenant_id: uuid.UUID, student_id: uuid.UUID) -> Student | None:
        statement = (
            self._base_query()
            .where(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
            .options(selectinload(Student.guardians).selectinload(StudentGuardian.guardian))
        )
        return cast(Student | None, await self.session.scalar(statement))

    async def get_by_admission_no(
        self,
        tenant_id: uuid.UUID,
        admission_no: str,
    ) -> Student | None:
        statement = self._base_query().where(
            Student.tenant_id == tenant_id,
            Student.admission_no == admission_no,
            Student.deleted_at.is_(None),
        )
        return cast(Student | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
        search: str | None,
        batch_id: uuid.UUID | None,
        sort: str,
    ) -> CursorResult[Student]:
        statement = self._base_query().where(
            Student.tenant_id == tenant_id,
            Student.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(Student.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Student.first_name.ilike(pattern),
                    Student.last_name.ilike(pattern),
                    Student.admission_no.ilike(pattern),
                    Student.email.ilike(pattern),
                    Student.phone.ilike(pattern),
                )
            )
        if batch_id is not None:
            statement = statement.join(BatchStudent).where(
                BatchStudent.batch_id == batch_id,
                BatchStudent.status == BatchStudentStatus.ACTIVE.value,
            )
        if cursor:
            created_at, entity_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    Student.created_at < created_at,
                    and_(Student.created_at == created_at, Student.id < entity_id),
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

    async def profile(self, tenant_id: uuid.UUID, student_id: uuid.UUID) -> Student | None:
        statement = (
            select(Student)
            .where(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
            .options(
                selectinload(Student.guardians).selectinload(StudentGuardian.guardian),
                selectinload(Student.batch_links),
                selectinload(Student.enrollments),
                selectinload(Student.notes),
                selectinload(Student.documents),
                selectinload(Student.status_history),
            )
        )
        return cast(Student | None, await self.session.scalar(statement))

    def _base_query(self) -> Select[tuple[Student]]:
        return select(Student)

    def _apply_sort(self, statement: Select[tuple[Student]], sort: str) -> Select[tuple[Student]]:
        if sort == "name":
            return statement.order_by(
                Student.first_name.asc(),
                Student.last_name.asc(),
                Student.id.desc(),
            )
        if sort == "admission_no":
            return statement.order_by(Student.admission_no.asc(), Student.id.desc())
        return statement.order_by(Student.created_at.desc(), Student.id.desc())


class GuardianRepository(Repository[Guardian]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Guardian)


class StudentGuardianRepository(Repository[StudentGuardian]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentGuardian)


class BatchRepository(Repository[Batch]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Batch)

    async def get_for_tenant(self, tenant_id: uuid.UUID, batch_id: uuid.UUID) -> Batch | None:
        statement = select(Batch).where(
            Batch.tenant_id == tenant_id,
            Batch.id == batch_id,
            Batch.deleted_at.is_(None),
        )
        return cast(Batch | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        status: str | None,
        search: str | None,
    ) -> Sequence[Batch]:
        statement = select(Batch).where(Batch.tenant_id == tenant_id, Batch.deleted_at.is_(None))
        if status is not None:
            statement = statement.where(Batch.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(or_(Batch.name.ilike(pattern), Batch.code.ilike(pattern)))
        statement = statement.order_by(Batch.start_date.desc(), Batch.name.asc())
        return (await self.session.scalars(statement)).all()


class BatchStudentRepository(Repository[BatchStudent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BatchStudent)

    async def get_membership(
        self,
        tenant_id: uuid.UUID,
        batch_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> BatchStudent | None:
        statement = select(BatchStudent).where(
            BatchStudent.tenant_id == tenant_id,
            BatchStudent.batch_id == batch_id,
            BatchStudent.student_id == student_id,
        )
        return cast(BatchStudent | None, await self.session.scalar(statement))

    async def active_count(self, tenant_id: uuid.UUID, batch_id: uuid.UUID) -> int:
        statement = select(func.count(BatchStudent.id)).where(
            BatchStudent.tenant_id == tenant_id,
            BatchStudent.batch_id == batch_id,
            BatchStudent.status == BatchStudentStatus.ACTIVE.value,
        )
        return int(await self.session.scalar(statement) or 0)


class StudentEnrollmentRepository(Repository[StudentEnrollment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentEnrollment)


class StudentNoteRepository(Repository[StudentNote]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentNote)


class StudentDocumentRepository(Repository[StudentDocument]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentDocument)


class StudentStatusHistoryRepository(Repository[StudentStatusHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StudentStatusHistory)
