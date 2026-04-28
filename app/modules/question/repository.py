from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.question.models import (
    AIQuestionGenerationJob,
    Question,
    QuestionOption,
    QuestionSet,
    QuestionSetItem,
    QuestionTag,
    QuestionTopic,
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


class QuestionTopicRepository(Repository[QuestionTopic]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QuestionTopic)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        topic_id: uuid.UUID,
    ) -> QuestionTopic | None:
        statement = select(QuestionTopic).where(
            QuestionTopic.tenant_id == tenant_id,
            QuestionTopic.id == topic_id,
        )
        return cast(QuestionTopic | None, await self.session.scalar(statement))

    async def get_by_slug(self, tenant_id: uuid.UUID, slug: str) -> QuestionTopic | None:
        statement = select(QuestionTopic).where(
            QuestionTopic.tenant_id == tenant_id,
            QuestionTopic.slug == slug,
        )
        return cast(QuestionTopic | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        search: str | None,
        include_archived: bool,
    ) -> list[QuestionTopic]:
        statement = select(QuestionTopic).where(QuestionTopic.tenant_id == tenant_id)
        if not include_archived:
            statement = statement.where(QuestionTopic.status == "active")
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    QuestionTopic.name.ilike(pattern),
                    QuestionTopic.slug.ilike(pattern),
                    QuestionTopic.description.ilike(pattern),
                )
            )
        statement = statement.order_by(QuestionTopic.name.asc(), QuestionTopic.id.asc())
        return list((await self.session.scalars(statement)).all())


class QuestionRepository(Repository[Question]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Question)

    async def get_for_tenant(self, tenant_id: uuid.UUID, question_id: uuid.UUID) -> Question | None:
        statement = (
            select(Question)
            .where(
                Question.tenant_id == tenant_id,
                Question.id == question_id,
                Question.deleted_at.is_(None),
            )
            .options(selectinload(Question.options), selectinload(Question.tags))
        )
        return cast(Question | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
        difficulty: str | None,
        question_type: str | None,
        topic_id: uuid.UUID | None,
        tag: str | None,
        search: str | None,
        sort: str,
    ) -> CursorResult[Question]:
        statement = (
            self._base_query()
            .where(Question.tenant_id == tenant_id, Question.deleted_at.is_(None))
            .options(selectinload(Question.options), selectinload(Question.tags))
        )
        if status is not None:
            statement = statement.where(Question.status == status)
        if difficulty is not None:
            statement = statement.where(Question.difficulty == difficulty)
        if question_type is not None:
            statement = statement.where(Question.question_type == question_type)
        if topic_id is not None:
            statement = statement.where(Question.topic_id == topic_id)
        if tag:
            normalized_tag = tag.strip().lower()
            statement = statement.where(Question.tags.any(QuestionTag.name == normalized_tag))
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Question.body.ilike(pattern),
                    Question.explanation.ilike(pattern),
                    Question.bloom_level.ilike(pattern),
                )
            )
        if cursor:
            created_at, entity_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    Question.created_at < created_at,
                    and_(Question.created_at == created_at, Question.id < entity_id),
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

    def _base_query(self) -> Select[tuple[Question]]:
        return select(Question)

    def _apply_sort(
        self,
        statement: Select[tuple[Question]],
        sort: str,
    ) -> Select[tuple[Question]]:
        if sort == "difficulty":
            return statement.order_by(Question.difficulty.asc(), Question.id.desc())
        if sort == "status":
            return statement.order_by(Question.status.asc(), Question.id.desc())
        return statement.order_by(Question.created_at.desc(), Question.id.desc())


class QuestionOptionRepository(Repository[QuestionOption]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QuestionOption)


class QuestionTagRepository(Repository[QuestionTag]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QuestionTag)


class QuestionSetRepository(Repository[QuestionSet]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QuestionSet)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        question_set_id: uuid.UUID,
    ) -> QuestionSet | None:
        statement = select(QuestionSet).where(
            QuestionSet.tenant_id == tenant_id,
            QuestionSet.id == question_set_id,
            QuestionSet.deleted_at.is_(None),
        )
        return cast(QuestionSet | None, await self.session.scalar(statement))

    async def detail(self, tenant_id: uuid.UUID, question_set_id: uuid.UUID) -> QuestionSet | None:
        statement = (
            select(QuestionSet)
            .where(
                QuestionSet.tenant_id == tenant_id,
                QuestionSet.id == question_set_id,
                QuestionSet.deleted_at.is_(None),
            )
            .options(
                selectinload(QuestionSet.items)
                .selectinload(QuestionSetItem.question)
                .selectinload(Question.options),
                selectinload(QuestionSet.items)
                .selectinload(QuestionSetItem.question)
                .selectinload(Question.tags),
            )
        )
        return cast(QuestionSet | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
        search: str | None,
        sort: str,
    ) -> CursorResult[QuestionSet]:
        statement = select(QuestionSet).where(
            QuestionSet.tenant_id == tenant_id,
            QuestionSet.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(QuestionSet.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(QuestionSet.title.ilike(pattern), QuestionSet.description.ilike(pattern))
            )
        if cursor:
            created_at, entity_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    QuestionSet.created_at < created_at,
                    and_(QuestionSet.created_at == created_at, QuestionSet.id < entity_id),
                )
            )
        if sort == "title":
            statement = statement.order_by(QuestionSet.title.asc(), QuestionSet.id.desc())
        else:
            statement = statement.order_by(QuestionSet.created_at.desc(), QuestionSet.id.desc())
        rows = list((await self.session.scalars(statement.limit(limit + 1))).all())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
        )
        return CursorResult(items=items, next_cursor=next_cursor, has_more=has_more)


class QuestionSetItemRepository(Repository[QuestionSetItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QuestionSetItem)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> QuestionSetItem | None:
        statement = (
            select(QuestionSetItem)
            .where(QuestionSetItem.tenant_id == tenant_id, QuestionSetItem.id == item_id)
            .options(
                selectinload(QuestionSetItem.question).selectinload(Question.options),
                selectinload(QuestionSetItem.question).selectinload(Question.tags),
            )
        )
        return cast(QuestionSetItem | None, await self.session.scalar(statement))

    async def get_assignment(
        self,
        tenant_id: uuid.UUID,
        question_set_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> QuestionSetItem | None:
        statement = select(QuestionSetItem).where(
            QuestionSetItem.tenant_id == tenant_id,
            QuestionSetItem.question_set_id == question_set_id,
            QuestionSetItem.question_id == question_id,
        )
        return cast(QuestionSetItem | None, await self.session.scalar(statement))

    async def list_for_set(
        self,
        tenant_id: uuid.UUID,
        question_set_id: uuid.UUID,
    ) -> list[QuestionSetItem]:
        statement = (
            select(QuestionSetItem)
            .where(
                QuestionSetItem.tenant_id == tenant_id,
                QuestionSetItem.question_set_id == question_set_id,
            )
            .options(
                selectinload(QuestionSetItem.question).selectinload(Question.options),
                selectinload(QuestionSetItem.question).selectinload(Question.tags),
            )
            .order_by(QuestionSetItem.order_index.asc(), QuestionSetItem.id.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def next_order_index(self, tenant_id: uuid.UUID, question_set_id: uuid.UUID) -> int:
        statement = select(func.max(QuestionSetItem.order_index)).where(
            QuestionSetItem.tenant_id == tenant_id,
            QuestionSetItem.question_set_id == question_set_id,
        )
        value = await self.session.scalar(statement)
        return int(value or 0) + 1


class AIQuestionGenerationJobRepository(Repository[AIQuestionGenerationJob]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AIQuestionGenerationJob)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> AIQuestionGenerationJob | None:
        statement = select(AIQuestionGenerationJob).where(
            AIQuestionGenerationJob.tenant_id == tenant_id,
            AIQuestionGenerationJob.id == job_id,
        )
        return cast(AIQuestionGenerationJob | None, await self.session.scalar(statement))
