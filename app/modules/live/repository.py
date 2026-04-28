from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.live.models import (
    LiveClass,
    LiveClassEvent,
    LiveClassParticipant,
    LiveClassRecording,
)
from app.shared.repository import Repository


@dataclass(frozen=True)
class CursorResult[T]:
    items: list[T]
    next_cursor: str | None
    has_more: bool


def encode_cursor(starts_at: datetime, entity_id: uuid.UUID) -> str:
    raw = f"{starts_at.isoformat()}|{entity_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    starts_at, entity_id = raw.split("|", maxsplit=1)
    return datetime.fromisoformat(starts_at), uuid.UUID(entity_id)


class LiveClassRepository(Repository[LiveClass]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LiveClass)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        live_class_id: uuid.UUID,
    ) -> LiveClass | None:
        statement = select(LiveClass).where(
            LiveClass.tenant_id == tenant_id,
            LiveClass.id == live_class_id,
        )
        return cast(LiveClass | None, await self.session.scalar(statement))

    async def get_by_code(self, class_code: str) -> LiveClass | None:
        statement = select(LiveClass).where(LiveClass.class_code == class_code)
        return cast(LiveClass | None, await self.session.scalar(statement))

    async def detail(self, tenant_id: uuid.UUID, live_class_id: uuid.UUID) -> LiveClass | None:
        statement = (
            select(LiveClass)
            .where(LiveClass.tenant_id == tenant_id, LiveClass.id == live_class_id)
            .options(
                selectinload(LiveClass.participants),
                selectinload(LiveClass.recordings),
                selectinload(LiveClass.events),
            )
        )
        return cast(LiveClass | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
        batch_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        teacher_id: uuid.UUID | None,
        starts_from: datetime | None,
        starts_to: datetime | None,
    ) -> CursorResult[LiveClass]:
        statement = select(LiveClass).where(LiveClass.tenant_id == tenant_id)
        if status is not None:
            statement = statement.where(LiveClass.status == status)
        if batch_id is not None:
            statement = statement.where(LiveClass.batch_id == batch_id)
        if teacher_id is not None:
            statement = statement.where(LiveClass.instructor_id == teacher_id)
        if starts_from is not None:
            statement = statement.where(LiveClass.starts_at >= starts_from)
        if starts_to is not None:
            statement = statement.where(LiveClass.starts_at <= starts_to)
        if student_id is not None:
            statement = statement.join(
                LiveClassParticipant,
                LiveClassParticipant.live_class_id == LiveClass.id,
            ).where(LiveClassParticipant.student_id == student_id)
        if cursor:
            starts_at, entity_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    LiveClass.starts_at > starts_at,
                    and_(LiveClass.starts_at == starts_at, LiveClass.id > entity_id),
                )
            )
        statement = self._apply_sort(statement).limit(limit + 1)
        rows = list((await self.session.scalars(statement)).all())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            encode_cursor(items[-1].starts_at, items[-1].id) if has_more and items else None
        )
        return CursorResult(items=items, next_cursor=next_cursor, has_more=has_more)

    def _apply_sort(self, statement: Select[tuple[LiveClass]]) -> Select[tuple[LiveClass]]:
        return statement.order_by(LiveClass.starts_at.asc(), LiveClass.id.asc())


class LiveClassParticipantRepository(Repository[LiveClassParticipant]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LiveClassParticipant)

    async def list_for_class(
        self,
        tenant_id: uuid.UUID,
        live_class_id: uuid.UUID,
    ) -> list[LiveClassParticipant]:
        statement = (
            select(LiveClassParticipant)
            .where(
                LiveClassParticipant.tenant_id == tenant_id,
                LiveClassParticipant.live_class_id == live_class_id,
            )
            .order_by(LiveClassParticipant.created_at.asc(), LiveClassParticipant.id.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def find_identity(
        self,
        tenant_id: uuid.UUID,
        live_class_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        employee_id: uuid.UUID | None,
    ) -> LiveClassParticipant | None:
        statement = select(LiveClassParticipant).where(
            LiveClassParticipant.tenant_id == tenant_id,
            LiveClassParticipant.live_class_id == live_class_id,
        )
        identity_filters = []
        if user_id is not None:
            identity_filters.append(LiveClassParticipant.user_id == user_id)
        if student_id is not None:
            identity_filters.append(LiveClassParticipant.student_id == student_id)
        if employee_id is not None:
            identity_filters.append(LiveClassParticipant.employee_id == employee_id)
        if not identity_filters:
            return None
        statement = statement.where(or_(*identity_filters))
        return cast(LiveClassParticipant | None, await self.session.scalar(statement))

    async def active_count(self, tenant_id: uuid.UUID, live_class_id: uuid.UUID) -> int:
        participants = await self.list_for_class(tenant_id, live_class_id)
        return sum(1 for participant in participants if participant.left_at is None)


class LiveClassRecordingRepository(Repository[LiveClassRecording]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LiveClassRecording)


class LiveClassEventRepository(Repository[LiveClassEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LiveClassEvent)
