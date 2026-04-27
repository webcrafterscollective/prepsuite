from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.learn.models import (
    Course,
    CourseBatch,
    CourseModule,
    CoursePrerequisite,
    CoursePublishHistory,
    CourseTeacher,
    Lesson,
    LessonResource,
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


class CourseRepository(Repository[Course]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Course)

    async def get_for_tenant(self, tenant_id: uuid.UUID, course_id: uuid.UUID) -> Course | None:
        statement = self._base_query().where(
            Course.tenant_id == tenant_id,
            Course.id == course_id,
            Course.deleted_at.is_(None),
        )
        return cast(Course | None, await self.session.scalar(statement))

    async def get_by_slug(self, tenant_id: uuid.UUID, slug: str) -> Course | None:
        statement = self._base_query().where(
            Course.tenant_id == tenant_id,
            Course.slug == slug,
            Course.deleted_at.is_(None),
        )
        return cast(Course | None, await self.session.scalar(statement))

    async def detail(self, tenant_id: uuid.UUID, course_id: uuid.UUID) -> Course | None:
        statement = (
            select(Course)
            .where(
                Course.tenant_id == tenant_id,
                Course.id == course_id,
                Course.deleted_at.is_(None),
            )
            .options(
                selectinload(Course.modules)
                .selectinload(CourseModule.lessons)
                .selectinload(Lesson.resources),
                selectinload(Course.batches),
                selectinload(Course.teachers),
                selectinload(Course.publish_history),
                selectinload(Course.prerequisites),
            )
        )
        return cast(Course | None, await self.session.scalar(statement))

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int,
        cursor: str | None,
        status: str | None,
        search: str | None,
        sort: str,
    ) -> CursorResult[Course]:
        statement = self._base_query().where(
            Course.tenant_id == tenant_id,
            Course.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(Course.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    Course.title.ilike(pattern),
                    Course.slug.ilike(pattern),
                    Course.description.ilike(pattern),
                    Course.category.ilike(pattern),
                )
            )
        if cursor:
            created_at, entity_id = decode_cursor(cursor)
            statement = statement.where(
                or_(
                    Course.created_at < created_at,
                    and_(Course.created_at == created_at, Course.id < entity_id),
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

    def _base_query(self) -> Select[tuple[Course]]:
        return select(Course)

    def _apply_sort(self, statement: Select[tuple[Course]], sort: str) -> Select[tuple[Course]]:
        if sort == "title":
            return statement.order_by(Course.title.asc(), Course.id.desc())
        if sort == "slug":
            return statement.order_by(Course.slug.asc(), Course.id.desc())
        return statement.order_by(Course.created_at.desc(), Course.id.desc())


class CourseModuleRepository(Repository[CourseModule]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CourseModule)

    async def get_for_tenant(
        self,
        tenant_id: uuid.UUID,
        module_id: uuid.UUID,
    ) -> CourseModule | None:
        statement = (
            select(CourseModule)
            .where(
                CourseModule.tenant_id == tenant_id,
                CourseModule.id == module_id,
                CourseModule.deleted_at.is_(None),
            )
            .options(selectinload(CourseModule.lessons).selectinload(Lesson.resources))
        )
        return cast(CourseModule | None, await self.session.scalar(statement))

    async def list_for_course(
        self,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> list[CourseModule]:
        statement = (
            select(CourseModule)
            .where(
                CourseModule.tenant_id == tenant_id,
                CourseModule.course_id == course_id,
                CourseModule.deleted_at.is_(None),
            )
            .order_by(CourseModule.order_index.asc(), CourseModule.id.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def next_order_index(self, tenant_id: uuid.UUID, course_id: uuid.UUID) -> int:
        statement = select(func.max(CourseModule.order_index)).where(
            CourseModule.tenant_id == tenant_id,
            CourseModule.course_id == course_id,
            CourseModule.deleted_at.is_(None),
        )
        value = await self.session.scalar(statement)
        return int(value or 0) + 1


class LessonRepository(Repository[Lesson]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Lesson)

    async def get_for_tenant(self, tenant_id: uuid.UUID, lesson_id: uuid.UUID) -> Lesson | None:
        statement = (
            select(Lesson)
            .where(
                Lesson.tenant_id == tenant_id,
                Lesson.id == lesson_id,
                Lesson.deleted_at.is_(None),
            )
            .options(selectinload(Lesson.resources))
        )
        return cast(Lesson | None, await self.session.scalar(statement))

    async def list_for_module(self, tenant_id: uuid.UUID, module_id: uuid.UUID) -> list[Lesson]:
        statement = (
            select(Lesson)
            .where(
                Lesson.tenant_id == tenant_id,
                Lesson.module_id == module_id,
                Lesson.deleted_at.is_(None),
            )
            .order_by(Lesson.order_index.asc(), Lesson.id.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def next_order_index(self, tenant_id: uuid.UUID, module_id: uuid.UUID) -> int:
        statement = select(func.max(Lesson.order_index)).where(
            Lesson.tenant_id == tenant_id,
            Lesson.module_id == module_id,
            Lesson.deleted_at.is_(None),
        )
        value = await self.session.scalar(statement)
        return int(value or 0) + 1


class LessonResourceRepository(Repository[LessonResource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LessonResource)


class CourseBatchRepository(Repository[CourseBatch]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CourseBatch)

    async def get_assignment(
        self,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID,
        batch_id: uuid.UUID,
    ) -> CourseBatch | None:
        statement = select(CourseBatch).where(
            CourseBatch.tenant_id == tenant_id,
            CourseBatch.course_id == course_id,
            CourseBatch.batch_id == batch_id,
        )
        return cast(CourseBatch | None, await self.session.scalar(statement))


class CourseTeacherRepository(Repository[CourseTeacher]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CourseTeacher)

    async def get_assignment(
        self,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> CourseTeacher | None:
        statement = select(CourseTeacher).where(
            CourseTeacher.tenant_id == tenant_id,
            CourseTeacher.course_id == course_id,
            CourseTeacher.teacher_id == teacher_id,
        )
        return cast(CourseTeacher | None, await self.session.scalar(statement))


class CoursePublishHistoryRepository(Repository[CoursePublishHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CoursePublishHistory)


class CoursePrerequisiteRepository(Repository[CoursePrerequisite]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CoursePrerequisite)
