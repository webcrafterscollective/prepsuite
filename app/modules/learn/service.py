from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import TenantContext
from app.modules.learn.enums import CourseAssignmentStatus, CourseStatus, LessonType
from app.modules.learn.models import (
    Course,
    CourseBatch,
    CourseModule,
    CoursePublishHistory,
    CourseTeacher,
    Lesson,
    LessonResource,
)
from app.modules.learn.repository import (
    CourseBatchRepository,
    CourseModuleRepository,
    CoursePrerequisiteRepository,
    CoursePublishHistoryRepository,
    CourseRepository,
    CourseTeacherRepository,
    LessonRepository,
    LessonResourceRepository,
)
from app.modules.learn.schemas import (
    CourseAssignBatchRequest,
    CourseAssignTeacherRequest,
    CourseBatchRead,
    CourseCreate,
    CourseDetailRead,
    CourseOutlineRead,
    CoursePage,
    CoursePrerequisiteRead,
    CoursePublishHistoryRead,
    CoursePublishRequest,
    CourseRead,
    CourseReorderRequest,
    CourseTeacherRead,
    CourseUpdate,
    LessonCreate,
    LessonRead,
    LessonResourceRead,
    LessonUpdate,
    ModuleCreate,
    ModuleRead,
    ModuleUpdate,
)
from app.modules.people.enums import EmployeeType
from app.modules.people.models import Employee
from app.modules.students.models import Batch


class PrepLearnService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.courses = CourseRepository(session)
        self.modules = CourseModuleRepository(session)
        self.lessons = LessonRepository(session)
        self.resources = LessonResourceRepository(session)
        self.course_batches = CourseBatchRepository(session)
        self.course_teachers = CourseTeacherRepository(session)
        self.publish_history = CoursePublishHistoryRepository(session)
        self.prerequisites = CoursePrerequisiteRepository(session)

    async def list_courses(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor: str | None,
        status: CourseStatus | None,
        search: str | None,
        sort: str,
    ) -> CoursePage:
        tenant_id = self._require_tenant_id(context)
        result = await self.courses.list_for_tenant(
            tenant_id,
            limit=limit,
            cursor=cursor,
            status=status.value if status else None,
            search=search,
            sort=sort,
        )
        return CoursePage(
            items=[CourseRead.model_validate(item) for item in result.items],
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    async def create_course(
        self,
        context: TenantContext,
        principal: Principal,
        payload: CourseCreate,
    ) -> Course:
        tenant_id = self._require_tenant_id(context)
        course = Course(
            tenant_id=tenant_id,
            created_by=principal.user_id,
            **payload.model_dump(mode="python"),
        )
        try:
            await self.courses.add(course)
            await self.session.refresh(course)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "course_conflict",
                "Course slug already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("course.created", context, principal, course.id)
        return course

    async def get_course(self, context: TenantContext, course_id: uuid.UUID) -> Course:
        tenant_id = self._require_tenant_id(context)
        course = await self.courses.get_for_tenant(tenant_id, course_id)
        if course is None:
            raise PrepSuiteError("course_not_found", "Course was not found.", status_code=404)
        return course

    async def get_detail(self, context: TenantContext, course_id: uuid.UUID) -> CourseDetailRead:
        tenant_id = self._require_tenant_id(context)
        course = await self.courses.detail(tenant_id, course_id)
        if course is None:
            raise PrepSuiteError("course_not_found", "Course was not found.", status_code=404)
        return self._detail_response(course)

    async def get_outline(self, context: TenantContext, course_id: uuid.UUID) -> CourseOutlineRead:
        detail = await self.get_detail(context, course_id)
        return CourseOutlineRead(course=detail.course, modules=detail.modules)

    async def update_course(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
        payload: CourseUpdate,
    ) -> Course:
        course = await self.get_course(context, course_id)
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        requested_status = update_data.pop("status", None)
        if requested_status == CourseStatus.PUBLISHED:
            raise PrepSuiteError(
                "course_publish_required",
                "Use the publish endpoint to publish a course.",
                status_code=409,
            )
        for field, value in update_data.items():
            setattr(course, field, value)
        if requested_status == CourseStatus.ARCHIVED:
            course.status = CourseStatus.ARCHIVED.value
        elif requested_status == CourseStatus.DRAFT:
            course.status = CourseStatus.DRAFT.value
            course.published_at = None
        try:
            await self.session.flush()
            await self.session.refresh(course)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "course_conflict",
                "Course slug already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("course.updated", context, principal, course.id)
        return course

    async def delete_course(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
    ) -> None:
        course = await self.get_course(context, course_id)
        course.deleted_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()
        await self._publish_event("course.deleted", context, principal, course.id)

    async def publish_course(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
        payload: CoursePublishRequest,
    ) -> CourseDetailRead:
        course = await self.get_course(context, course_id)
        if course.status == CourseStatus.ARCHIVED.value:
            raise PrepSuiteError(
                "course_archived",
                "Archived courses cannot be published.",
                status_code=409,
            )
        await self._assert_publishable(course)
        previous_status = course.status
        course.status = CourseStatus.PUBLISHED.value
        course.published_at = datetime.now(UTC)
        history = CoursePublishHistory(
            tenant_id=course.tenant_id,
            course_id=course.id,
            published_by=principal.user_id,
            previous_status=previous_status,
            new_status=CourseStatus.PUBLISHED.value,
            published_at=course.published_at,
            notes=payload.notes,
        )
        await self.publish_history.add(history)
        await self.session.flush()
        detail = await self._detail_response_for(course.tenant_id, course.id)
        await self.session.commit()
        await self._publish_event("course.published", context, principal, course.id)
        return detail

    async def archive_course(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
    ) -> Course:
        course = await self.get_course(context, course_id)
        course.status = CourseStatus.ARCHIVED.value
        await self.session.flush()
        await self.session.refresh(course)
        await self.session.commit()
        await self._publish_event("course.archived", context, principal, course.id)
        return course

    async def create_module(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
        payload: ModuleCreate,
    ) -> ModuleRead:
        tenant_id = self._require_tenant_id(context)
        course = await self.get_course(context, course_id)
        order_index = payload.order_index
        if order_index is None:
            order_index = await self.modules.next_order_index(tenant_id, course.id)
        module = CourseModule(
            tenant_id=tenant_id,
            course_id=course.id,
            title=payload.title,
            description=payload.description,
            order_index=order_index,
        )
        try:
            await self.modules.add(module)
            await self.session.refresh(module)
            response = await self._module_response(tenant_id, module.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "module_order_conflict",
                "Module order already exists for this course.",
                status_code=409,
            ) from exc
        await self._publish_event("course.module.created", context, principal, module.id)
        return response

    async def update_module(
        self,
        context: TenantContext,
        principal: Principal,
        module_id: uuid.UUID,
        payload: ModuleUpdate,
    ) -> ModuleRead:
        tenant_id = self._require_tenant_id(context)
        module = await self._get_module_or_raise(tenant_id, module_id)
        for field, value in payload.model_dump(exclude_unset=True, mode="python").items():
            setattr(module, field, value)
        try:
            await self.session.flush()
            await self.session.refresh(module)
            response = await self._module_response(tenant_id, module.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "module_order_conflict",
                "Module order already exists for this course.",
                status_code=409,
            ) from exc
        await self._publish_event("course.module.updated", context, principal, module.id)
        return response

    async def create_lesson(
        self,
        context: TenantContext,
        principal: Principal,
        module_id: uuid.UUID,
        payload: LessonCreate,
    ) -> LessonRead:
        tenant_id = self._require_tenant_id(context)
        module = await self._get_module_or_raise(tenant_id, module_id)
        order_index = payload.order_index
        if order_index is None:
            order_index = await self.lessons.next_order_index(tenant_id, module.id)
        lesson = Lesson(
            tenant_id=tenant_id,
            module_id=module.id,
            title=payload.title,
            lesson_type=payload.lesson_type.value,
            content=payload.content,
            duration_minutes=payload.duration_minutes,
            order_index=order_index,
            is_preview=payload.is_preview,
            completion_rule=payload.completion_rule,
        )
        self.session.add(lesson)
        await self.session.flush()
        for index, resource_payload in enumerate(payload.resources, start=1):
            resource_data = resource_payload.model_dump(mode="python")
            metadata = resource_data.pop("metadata", {})
            resource_order = resource_data.pop("order_index") or index
            self.session.add(
                LessonResource(
                    tenant_id=tenant_id,
                    lesson_id=lesson.id,
                    metadata_=metadata,
                    order_index=resource_order,
                    **resource_data,
                )
            )
        try:
            await self.session.flush()
            await self.session.refresh(lesson, attribute_names=["resources"])
            response = await self._lesson_response(tenant_id, lesson.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "lesson_order_conflict",
                "Lesson order already exists for this module.",
                status_code=409,
            ) from exc
        await self._publish_event("course.lesson.created", context, principal, lesson.id)
        return response

    async def update_lesson(
        self,
        context: TenantContext,
        principal: Principal,
        lesson_id: uuid.UUID,
        payload: LessonUpdate,
    ) -> LessonRead:
        tenant_id = self._require_tenant_id(context)
        lesson = await self._get_lesson_or_raise(tenant_id, lesson_id)
        for field, value in payload.model_dump(exclude_unset=True, mode="python").items():
            setattr(lesson, field, value.value if hasattr(value, "value") else value)
        try:
            await self.session.flush()
            await self.session.refresh(lesson)
            response = await self._lesson_response(tenant_id, lesson.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "lesson_order_conflict",
                "Lesson order already exists for this module.",
                status_code=409,
            ) from exc
        await self._publish_event("course.lesson.updated", context, principal, lesson.id)
        return response

    async def reorder_course(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
        payload: CourseReorderRequest,
    ) -> CourseDetailRead:
        tenant_id = self._require_tenant_id(context)
        course = await self.get_course(context, course_id)
        module_ids = [item.module_id for item in payload.modules]
        if len(module_ids) != len(set(module_ids)):
            raise PrepSuiteError(
                "duplicate_module_order",
                "Module IDs must be unique.",
                status_code=422,
            )
        lesson_ids = [item.lesson_id for item in payload.lessons]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise PrepSuiteError(
                "duplicate_lesson_order",
                "Lesson IDs must be unique.",
                status_code=422,
            )

        modules = [
            await self._get_module_or_raise(tenant_id, item.module_id)
            for item in payload.modules
        ]
        for module in modules:
            if module.course_id != course.id:
                raise PrepSuiteError("module_not_found", "Module was not found.", status_code=404)
        lessons = [
            await self._get_lesson_or_raise(tenant_id, item.lesson_id)
            for item in payload.lessons
        ]
        course_modules = await self.modules.list_for_course(tenant_id, course.id)
        module_by_id = {module.id: module for module in course_modules}
        for lesson in lessons:
            if lesson.module_id not in module_by_id:
                raise PrepSuiteError("lesson_not_found", "Lesson was not found.", status_code=404)

        for index, module in enumerate(modules, start=1):
            module.order_index = 100000 + index
        for index, lesson in enumerate(lessons, start=1):
            lesson.order_index = 100000 + index
        await self.session.flush()
        for module_item in payload.modules:
            module_by_id[module_item.module_id].order_index = module_item.order_index
        lesson_by_id = {lesson.id: lesson for lesson in lessons}
        for lesson_item in payload.lessons:
            lesson_by_id[lesson_item.lesson_id].order_index = lesson_item.order_index
        await self.session.flush()
        detail = await self._detail_response_for(tenant_id, course.id)
        await self.session.commit()
        await self._publish_event("course.reordered", context, principal, course.id)
        return detail

    async def assign_batch(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
        payload: CourseAssignBatchRequest,
    ) -> CourseBatch:
        tenant_id = self._require_tenant_id(context)
        course = await self.get_course(context, course_id)
        await self._validate_batch(tenant_id, payload.batch_id)
        existing = await self.course_batches.get_assignment(tenant_id, course.id, payload.batch_id)
        if existing is not None:
            existing.status = CourseAssignmentStatus.ACTIVE.value
            await self.session.flush()
            await self.session.refresh(existing)
            await self.session.commit()
            return existing
        assignment = CourseBatch(
            tenant_id=tenant_id,
            course_id=course.id,
            batch_id=payload.batch_id,
        )
        await self.course_batches.add(assignment)
        await self.session.refresh(assignment)
        await self.session.commit()
        await self._publish_event("course.batch_assigned", context, principal, assignment.id)
        return assignment

    async def assign_teacher(
        self,
        context: TenantContext,
        principal: Principal,
        course_id: uuid.UUID,
        payload: CourseAssignTeacherRequest,
    ) -> CourseTeacher:
        tenant_id = self._require_tenant_id(context)
        course = await self.get_course(context, course_id)
        await self._validate_teacher(tenant_id, payload.teacher_id)
        existing = await self.course_teachers.get_assignment(
            tenant_id,
            course.id,
            payload.teacher_id,
        )
        if existing is not None:
            existing.status = CourseAssignmentStatus.ACTIVE.value
            await self.session.flush()
            await self.session.refresh(existing)
            await self.session.commit()
            return existing
        assignment = CourseTeacher(
            tenant_id=tenant_id,
            course_id=course.id,
            teacher_id=payload.teacher_id,
        )
        await self.course_teachers.add(assignment)
        await self.session.refresh(assignment)
        await self.session.commit()
        await self._publish_event("course.teacher_assigned", context, principal, assignment.id)
        return assignment

    async def _module_response(self, tenant_id: uuid.UUID, module_id: uuid.UUID) -> ModuleRead:
        module = await self._get_module_or_raise(tenant_id, module_id)
        return self._module_read(module)

    async def _lesson_response(self, tenant_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonRead:
        lesson = await self._get_lesson_or_raise(tenant_id, lesson_id)
        return self._lesson_read(lesson)

    async def _detail_response_for(
        self,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> CourseDetailRead:
        course = await self.courses.detail(tenant_id, course_id)
        if course is None:
            raise PrepSuiteError("course_not_found", "Course was not found.", status_code=404)
        return self._detail_response(course)

    async def _assert_publishable(self, course: Course) -> None:
        modules = await self.modules.list_for_course(course.tenant_id, course.id)
        if not modules:
            raise PrepSuiteError(
                "course_publish_requirements_not_met",
                "A course must have at least one module before publishing.",
                status_code=409,
            )
        for module in modules:
            lessons = await self.lessons.list_for_module(course.tenant_id, module.id)
            if not lessons:
                raise PrepSuiteError(
                    "course_publish_requirements_not_met",
                    "Every module must have at least one lesson before publishing.",
                    status_code=409,
                    details={"module_id": str(module.id)},
                )

    async def _get_module_or_raise(
        self,
        tenant_id: uuid.UUID,
        module_id: uuid.UUID,
    ) -> CourseModule:
        module = await self.modules.get_for_tenant(tenant_id, module_id)
        if module is None:
            raise PrepSuiteError("module_not_found", "Module was not found.", status_code=404)
        return module

    async def _get_lesson_or_raise(self, tenant_id: uuid.UUID, lesson_id: uuid.UUID) -> Lesson:
        lesson = await self.lessons.get_for_tenant(tenant_id, lesson_id)
        if lesson is None:
            raise PrepSuiteError("lesson_not_found", "Lesson was not found.", status_code=404)
        return lesson

    async def _validate_batch(self, tenant_id: uuid.UUID, batch_id: uuid.UUID) -> None:
        statement = select(Batch.id).where(
            Batch.tenant_id == tenant_id,
            Batch.id == batch_id,
            Batch.deleted_at.is_(None),
        )
        if await self.session.scalar(statement) is None:
            raise PrepSuiteError("batch_not_found", "Batch was not found.", status_code=404)

    async def _validate_teacher(self, tenant_id: uuid.UUID, teacher_id: uuid.UUID) -> None:
        statement = select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.id == teacher_id,
            Employee.deleted_at.is_(None),
        )
        teacher = await self.session.scalar(statement)
        if teacher is None:
            raise PrepSuiteError("teacher_not_found", "Teacher was not found.", status_code=404)
        if teacher.employee_type != EmployeeType.TEACHER.value:
            raise PrepSuiteError(
                "employee_not_teacher",
                "Only teacher employees can be assigned to a course.",
                status_code=422,
                details={"employee_id": str(teacher.id)},
            )

    def _detail_response(self, course: Course) -> CourseDetailRead:
        modules = sorted(
            (module for module in course.modules if module.deleted_at is None),
            key=lambda item: (item.order_index, item.id),
        )
        return CourseDetailRead(
            course=CourseRead.model_validate(course),
            modules=[self._module_read(module) for module in modules],
            batches=[
                CourseBatchRead.model_validate(item)
                for item in sorted(course.batches, key=lambda record: record.created_at)
            ],
            teachers=[
                CourseTeacherRead.model_validate(item)
                for item in sorted(course.teachers, key=lambda record: record.created_at)
            ],
            publish_history=[
                CoursePublishHistoryRead.model_validate(item)
                for item in sorted(
                    course.publish_history,
                    key=lambda record: record.published_at,
                    reverse=True,
                )
            ],
            prerequisites=[
                CoursePrerequisiteRead.model_validate(item)
                for item in sorted(course.prerequisites, key=lambda record: record.created_at)
            ],
        )

    def _module_read(self, module: CourseModule) -> ModuleRead:
        lessons = sorted(
            (lesson for lesson in module.lessons if lesson.deleted_at is None),
            key=lambda item: (item.order_index, item.id),
        )
        return ModuleRead(
            id=module.id,
            tenant_id=module.tenant_id,
            course_id=module.course_id,
            title=module.title,
            description=module.description,
            order_index=module.order_index,
            lessons=[self._lesson_read(lesson) for lesson in lessons],
            created_at=module.created_at,
            updated_at=module.updated_at,
            deleted_at=module.deleted_at,
        )

    def _lesson_read(self, lesson: Lesson) -> LessonRead:
        resources = sorted(
            (resource for resource in lesson.resources if resource.deleted_at is None),
            key=lambda item: (item.order_index, item.id),
        )
        return LessonRead(
            id=lesson.id,
            tenant_id=lesson.tenant_id,
            module_id=lesson.module_id,
            title=lesson.title,
            lesson_type=LessonType(lesson.lesson_type),
            content=lesson.content,
            duration_minutes=lesson.duration_minutes,
            order_index=lesson.order_index,
            is_preview=lesson.is_preview,
            completion_rule=lesson.completion_rule,
            resources=[LessonResourceRead.model_validate(resource) for resource in resources],
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
            deleted_at=lesson.deleted_at,
        )

    async def _publish_event(
        self,
        event_type: str,
        context: TenantContext,
        principal: Principal,
        entity_id: uuid.UUID,
    ) -> None:
        await self.dispatcher.publish(
            DomainEvent(
                event_type=event_type,
                tenant_id=context.tenant_id,
                payload={"actor_user_id": str(principal.user_id), "entity_id": str(entity_id)},
            )
        )

    def _require_tenant_id(self, context: TenantContext) -> uuid.UUID:
        if context.tenant_id is None:
            raise PrepSuiteError("tenant_required", "Tenant context is required.", status_code=400)
        return context.tenant_id
