from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.assess.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentQuestion,
    AssessmentResult,
    AssessmentSection,
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


class AssessmentRepository(Repository[Assessment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Assessment)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> Assessment | None:
        statement = select(Assessment).where(
            Assessment.tenant_id == tenant_id,
            Assessment.id == assessment_id,
            Assessment.deleted_at.is_(None),
        )
        return cast(Assessment | None, await self.session.scalar(statement))

    async def detail(self, tenant_id: uuid.UUID, assessment_id: uuid.UUID) -> Assessment | None:
        statement = (
            select(Assessment)
            .where(
                Assessment.tenant_id == tenant_id,
                Assessment.id == assessment_id,
                Assessment.deleted_at.is_(None),
            )
            .options(
                selectinload(Assessment.sections),
                selectinload(Assessment.questions),
                selectinload(Assessment.attempts),
                selectinload(Assessment.results),
            )
        )
        return cast(Assessment | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
        assessment_type: str | None,
        course_id: uuid.UUID | None,
        batch_id: uuid.UUID | None,
        search: str | None,
        sort: str,
    ) -> CursorResult[Assessment]:
        statement = select(Assessment).where(
            Assessment.tenant_id == tenant_id,
            Assessment.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(Assessment.status == status)
        if assessment_type is not None:
            statement = statement.where(Assessment.type == assessment_type)
        if course_id is not None:
            statement = statement.where(Assessment.course_id == course_id)
        if batch_id is not None:
            statement = statement.where(Assessment.batch_id == batch_id)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(Assessment.title.ilike(pattern))
        if cursor:
            created_at, entity_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    Assessment.created_at < created_at,
                    and_(Assessment.created_at == created_at, Assessment.id < entity_id),
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

    def _apply_sort(
        self,
        statement: Select[tuple[Assessment]],
        sort: str,
    ) -> Select[tuple[Assessment]]:
        if sort == "starts_at":
            return statement.order_by(Assessment.starts_at.asc().nulls_last(), Assessment.id.desc())
        if sort == "title":
            return statement.order_by(Assessment.title.asc(), Assessment.id.desc())
        return statement.order_by(Assessment.created_at.desc(), Assessment.id.desc())


class AssessmentSectionRepository(Repository[AssessmentSection]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssessmentSection)


class AssessmentQuestionRepository(Repository[AssessmentQuestion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssessmentQuestion)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        assessment_question_id: uuid.UUID,
    ) -> AssessmentQuestion | None:
        statement = select(AssessmentQuestion).where(
            AssessmentQuestion.tenant_id == tenant_id,
            AssessmentQuestion.id == assessment_question_id,
        )
        return cast(AssessmentQuestion | None, await self.session.scalar(statement))

    async def list_for_assessment(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> list[AssessmentQuestion]:
        statement = (
            select(AssessmentQuestion)
            .where(
                AssessmentQuestion.tenant_id == tenant_id,
                AssessmentQuestion.assessment_id == assessment_id,
            )
            .order_by(AssessmentQuestion.order_index.asc(), AssessmentQuestion.id.asc())
        )
        return list((await self.session.scalars(statement)).all())


class AssessmentAttemptRepository(Repository[AssessmentAttempt]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssessmentAttempt)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        attempt_id: uuid.UUID,
    ) -> AssessmentAttempt | None:
        statement = (
            select(AssessmentAttempt)
            .where(AssessmentAttempt.tenant_id == tenant_id, AssessmentAttempt.id == attempt_id)
            .options(selectinload(AssessmentAttempt.answers))
        )
        return cast(AssessmentAttempt | None, await self.session.scalar(statement))

    async def get_for_student(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> AssessmentAttempt | None:
        statement = (
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.tenant_id == tenant_id,
                AssessmentAttempt.assessment_id == assessment_id,
                AssessmentAttempt.student_id == student_id,
            )
            .options(selectinload(AssessmentAttempt.answers))
        )
        return cast(AssessmentAttempt | None, await self.session.scalar(statement))

    async def list_for_assessment(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> list[AssessmentAttempt]:
        statement = select(AssessmentAttempt).where(
            AssessmentAttempt.tenant_id == tenant_id,
            AssessmentAttempt.assessment_id == assessment_id,
        )
        return list((await self.session.scalars(statement)).all())


class AssessmentAnswerRepository(Repository[AssessmentAnswer]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssessmentAnswer)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        answer_id: uuid.UUID,
    ) -> AssessmentAnswer | None:
        statement = select(AssessmentAnswer).where(
            AssessmentAnswer.tenant_id == tenant_id,
            AssessmentAnswer.id == answer_id,
        )
        return cast(AssessmentAnswer | None, await self.session.scalar(statement))

    async def get_for_attempt_question(
        self,
        tenant_id: uuid.UUID,
        attempt_id: uuid.UUID,
        assessment_question_id: uuid.UUID,
    ) -> AssessmentAnswer | None:
        statement = select(AssessmentAnswer).where(
            AssessmentAnswer.tenant_id == tenant_id,
            AssessmentAnswer.attempt_id == attempt_id,
            AssessmentAnswer.assessment_question_id == assessment_question_id,
        )
        return cast(AssessmentAnswer | None, await self.session.scalar(statement))

    async def pending_for_assessment(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> list[AssessmentAnswer]:
        statement = (
            select(AssessmentAnswer)
            .join(
                AssessmentQuestion,
                AssessmentQuestion.id == AssessmentAnswer.assessment_question_id,
            )
            .where(
                AssessmentAnswer.tenant_id == tenant_id,
                AssessmentQuestion.assessment_id == assessment_id,
                AssessmentAnswer.status == "pending",
            )
            .order_by(AssessmentAnswer.created_at.asc(), AssessmentAnswer.id.asc())
        )
        return list((await self.session.scalars(statement)).all())


class AssessmentResultRepository(Repository[AssessmentResult]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssessmentResult)

    async def get_for_attempt(
        self,
        tenant_id: uuid.UUID,
        attempt_id: uuid.UUID,
    ) -> AssessmentResult | None:
        statement = select(AssessmentResult).where(
            AssessmentResult.tenant_id == tenant_id,
            AssessmentResult.attempt_id == attempt_id,
        )
        return cast(AssessmentResult | None, await self.session.scalar(statement))

    async def list_for_assessment(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> list[AssessmentResult]:
        statement = select(AssessmentResult).where(
            AssessmentResult.tenant_id == tenant_id,
            AssessmentResult.assessment_id == assessment_id,
        )
        return list((await self.session.scalars(statement)).all())
