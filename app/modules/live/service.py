from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import TenantContext
from app.modules.learn.enums import CourseAssignmentStatus
from app.modules.learn.models import Course, CourseBatch, CourseTeacher
from app.modules.live.enums import (
    LiveClassEventType,
    LiveClassStatus,
    LiveJoinStatus,
    LiveParticipantRole,
    LiveProvider,
)
from app.modules.live.models import (
    LiveClass,
    LiveClassAttendanceSnapshot,
    LiveClassEvent,
    LiveClassParticipant,
    LiveClassRecording,
)
from app.modules.live.repository import (
    LiveClassEventRepository,
    LiveClassParticipantRepository,
    LiveClassRecordingRepository,
    LiveClassRepository,
)
from app.modules.live.schemas import (
    LiveAccessValidationRead,
    LiveAccessValidationRequest,
    LiveAttendanceEventsRead,
    LiveAttendanceEventsRequest,
    LiveClassCancelRequest,
    LiveClassCreate,
    LiveClassDetailRead,
    LiveClassEventRead,
    LiveClassPage,
    LiveClassParticipantRead,
    LiveClassRead,
    LiveClassRecordingCreate,
    LiveClassRecordingRead,
    LiveClassUpdate,
)
from app.modules.people.enums import EmployeeStatus, EmployeeType, TeacherAssignmentStatus
from app.modules.people.models import Employee, TeacherAssignment
from app.modules.students.models import Batch, BatchStudent, Student

LIVE_LINK_BASE_URL = "https://live.prepsuite.in"
SCHEDULABLE_STATUSES = {LiveClassStatus.SCHEDULED.value, LiveClassStatus.OPEN.value}
JOINABLE_STATUSES = {
    LiveClassStatus.SCHEDULED.value,
    LiveClassStatus.OPEN.value,
    LiveClassStatus.LIVE.value,
}


class PrepLiveService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.live_classes = LiveClassRepository(session)
        self.participants = LiveClassParticipantRepository(session)
        self.recordings = LiveClassRecordingRepository(session)
        self.events = LiveClassEventRepository(session)

    async def schedule_class(
        self,
        context: TenantContext,
        principal: Principal,
        payload: LiveClassCreate,
    ) -> LiveClassRead:
        tenant_id = self._require_tenant_id(context)
        self._assert_admin_override_allowed(principal, payload.admin_override)
        await self._validate_batch(tenant_id, payload.batch_id)
        await self._validate_optional_course_batch(tenant_id, payload.course_id, payload.batch_id)
        await self._validate_instructor(
            tenant_id,
            payload.instructor_id,
            course_id=payload.course_id,
            batch_id=payload.batch_id,
            admin_override=payload.admin_override,
        )
        live_class = LiveClass(
            tenant_id=tenant_id,
            class_code=await self._generate_class_code(payload.title),
            title=payload.title,
            description=payload.description,
            course_id=payload.course_id,
            batch_id=payload.batch_id,
            instructor_id=payload.instructor_id,
            starts_at=self._coerce_datetime(payload.starts_at),
            ends_at=self._coerce_datetime(payload.ends_at),
            duration_minutes=payload.duration_minutes,
            join_before_minutes=payload.join_before_minutes,
            join_after_minutes=payload.join_after_minutes,
            capacity=payload.capacity,
            live_provider=LiveProvider.MEDIASOUP.value,
            link="",
            settings=payload.settings,
            created_by=principal.user_id,
        )
        live_class.link = self._live_link(live_class.class_code)
        try:
            await self.live_classes.add(live_class)
            self.session.add(
                LiveClassParticipant(
                    tenant_id=tenant_id,
                    live_class_id=live_class.id,
                    user_id=principal.user_id,
                    employee_id=payload.instructor_id,
                    participant_role=LiveParticipantRole.INSTRUCTOR.value,
                    join_status=LiveJoinStatus.ALLOWED.value,
                )
            )
            await self._record_class_event(
                tenant_id,
                live_class.id,
                LiveClassEventType.SCHEDULED.value,
                {"created_by": str(principal.user_id)},
            )
            await self.session.flush()
            await self.session.refresh(live_class)
            response = self._class_read(live_class)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "live_class_conflict",
                "Live class could not be scheduled due to conflicting data.",
                status_code=409,
            ) from exc
        await self._publish_event(
            LiveClassEventType.SCHEDULED.value,
            context,
            principal,
            live_class.id,
        )
        return response

    async def list_classes(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor: str | None,
        status: LiveClassStatus | None,
        batch_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        teacher_id: uuid.UUID | None,
        starts_from: datetime | None,
        starts_to: datetime | None,
    ) -> LiveClassPage:
        tenant_id = self._require_tenant_id(context)
        result = await self.live_classes.list_for_tenant(
            tenant_id,
            limit=limit,
            cursor=cursor,
            status=status.value if status else None,
            batch_id=batch_id,
            student_id=student_id,
            teacher_id=teacher_id,
            starts_from=self._coerce_datetime(starts_from) if starts_from else None,
            starts_to=self._coerce_datetime(starts_to) if starts_to else None,
        )
        return LiveClassPage(
            items=[self._class_read(live_class) for live_class in result.items],
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    async def get_class(
        self,
        context: TenantContext,
        live_class_id: uuid.UUID,
    ) -> LiveClassDetailRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self._get_detail_or_raise(tenant_id, live_class_id)
        return self._class_detail_read(live_class)

    async def get_by_code(
        self,
        context: TenantContext,
        class_code: str,
    ) -> LiveClassDetailRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self.live_classes.get_by_code(class_code)
        if live_class is None or live_class.tenant_id != tenant_id:
            raise PrepSuiteError(
                "live_class_not_found",
                "Live class was not found.",
                status_code=404,
            )
        detail = await self._get_detail_or_raise(tenant_id, live_class.id)
        return self._class_detail_read(detail)

    async def update_class(
        self,
        context: TenantContext,
        principal: Principal,
        live_class_id: uuid.UUID,
        payload: LiveClassUpdate,
    ) -> LiveClassRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self._get_class_or_raise(tenant_id, live_class_id)
        if live_class.status not in SCHEDULABLE_STATUSES:
            raise PrepSuiteError(
                "live_class_locked",
                "Only scheduled or open live classes can be updated.",
                status_code=409,
            )
        self._assert_admin_override_allowed(principal, payload.admin_override)
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        next_batch_id = update_data.get("batch_id", live_class.batch_id)
        next_course_id = update_data.get("course_id", live_class.course_id)
        next_instructor_id = update_data.get("instructor_id", live_class.instructor_id)
        if "batch_id" in update_data:
            await self._validate_batch(tenant_id, next_batch_id)
        if "course_id" in update_data or "batch_id" in update_data:
            await self._validate_optional_course_batch(tenant_id, next_course_id, next_batch_id)
        if (
            "instructor_id" in update_data
            or "course_id" in update_data
            or "batch_id" in update_data
        ):
            await self._validate_instructor(
                tenant_id,
                next_instructor_id,
                course_id=next_course_id,
                batch_id=next_batch_id,
                admin_override=payload.admin_override,
            )
        for field, value in update_data.items():
            if field == "admin_override":
                continue
            if field in {"starts_at", "ends_at"}:
                value = self._coerce_datetime(value)
            setattr(live_class, field, value)
        self._assert_live_class_time_window(live_class.starts_at, live_class.ends_at)
        await self.session.flush()
        await self.session.refresh(live_class)
        response = self._class_read(live_class)
        await self.session.commit()
        await self._publish_event("live.class.updated", context, principal, live_class.id)
        return response

    async def cancel_class(
        self,
        context: TenantContext,
        principal: Principal,
        live_class_id: uuid.UUID,
        payload: LiveClassCancelRequest,
    ) -> LiveClassRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self._get_class_or_raise(tenant_id, live_class_id)
        if live_class.status in {LiveClassStatus.ENDED.value, LiveClassStatus.CANCELLED.value}:
            raise PrepSuiteError(
                "live_class_closed",
                "Live class is already closed.",
                status_code=409,
            )
        live_class.status = LiveClassStatus.CANCELLED.value
        await self._record_class_event(
            tenant_id,
            live_class.id,
            LiveClassEventType.CANCELLED.value,
            {"reason": payload.reason},
        )
        await self.session.flush()
        await self.session.refresh(live_class)
        response = self._class_read(live_class)
        await self.session.commit()
        await self._publish_event(
            LiveClassEventType.CANCELLED.value,
            context,
            principal,
            live_class.id,
        )
        return response

    async def open_class(
        self,
        context: TenantContext,
        principal: Principal,
        live_class_id: uuid.UUID,
    ) -> LiveClassRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self._get_class_or_raise(tenant_id, live_class_id)
        if live_class.status != LiveClassStatus.SCHEDULED.value:
            raise PrepSuiteError(
                "live_class_open_not_allowed",
                "Only scheduled live classes can be opened.",
                status_code=409,
            )
        live_class.status = LiveClassStatus.OPEN.value
        await self._record_class_event(
            tenant_id,
            live_class.id,
            LiveClassEventType.STARTED.value,
            {"status": LiveClassStatus.OPEN.value},
        )
        await self.session.flush()
        await self.session.refresh(live_class)
        response = self._class_read(live_class)
        await self.session.commit()
        await self._publish_event(
            LiveClassEventType.STARTED.value,
            context,
            principal,
            live_class.id,
        )
        return response

    async def end_class(
        self,
        context: TenantContext,
        principal: Principal,
        live_class_id: uuid.UUID,
    ) -> LiveClassRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self._get_class_or_raise(tenant_id, live_class_id)
        if live_class.status == LiveClassStatus.ENDED.value:
            return self._class_read(live_class)
        if live_class.status == LiveClassStatus.CANCELLED.value:
            raise PrepSuiteError(
                "live_class_cancelled",
                "Cancelled live classes cannot be ended.",
                status_code=409,
            )
        live_class.status = LiveClassStatus.ENDED.value
        participants = await self.participants.list_for_class(tenant_id, live_class.id)
        now = datetime.now(UTC)
        for participant in participants:
            if participant.joined_at is not None and participant.left_at is None:
                participant.left_at = now
                participant.join_status = LiveJoinStatus.COMPLETED.value
                participant.total_duration_seconds += self._duration_seconds(
                    participant.joined_at,
                    now,
                )
        await self._record_class_event(tenant_id, live_class.id, LiveClassEventType.ENDED.value, {})
        await self.session.flush()
        await self.session.refresh(live_class)
        response = self._class_read(live_class)
        await self.session.commit()
        await self._publish_event(LiveClassEventType.ENDED.value, context, principal, live_class.id)
        return response

    async def validate_access(
        self,
        context: TenantContext,
        principal: Principal,
        class_code: str,
        payload: LiveAccessValidationRequest,
    ) -> LiveAccessValidationRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self.live_classes.get_by_code(class_code)
        if live_class is None or live_class.tenant_id != tenant_id:
            raise PrepSuiteError(
                "live_class_not_found",
                "Live class was not found.",
                status_code=404,
            )
        join_start, join_end = self._join_window(live_class)
        now = self._coerce_datetime(payload.now) if payload.now else datetime.now(UTC)
        denied_reason = await self._access_denial_reason(
            tenant_id,
            principal,
            live_class,
            payload,
            now,
            join_start,
            join_end,
        )
        if denied_reason is not None:
            return LiveAccessValidationRead(
                allowed=False,
                reason=denied_reason,
                live_class=self._class_read(live_class),
                participant=None,
                join_window_starts_at=join_start,
                join_window_ends_at=join_end,
            )
        participant = await self._upsert_allowed_participant(
            tenant_id,
            live_class,
            user_id=self._validation_user_id(principal, payload),
            student_id=payload.student_id,
            employee_id=payload.employee_id,
            role=payload.participant_role or self._infer_role(live_class, payload),
            joined_at=now,
        )
        await self._record_class_event(
            tenant_id,
            live_class.id,
            LiveClassEventType.PARTICIPANT_JOINED.value,
            {"participant_id": str(participant.id)},
            participant_id=participant.id,
            occurred_at=now,
        )
        await self.session.flush()
        await self.session.refresh(participant)
        response = LiveAccessValidationRead(
            allowed=True,
            reason=None,
            live_class=self._class_read(live_class),
            participant=self._participant_read(participant),
            join_window_starts_at=join_start,
            join_window_ends_at=join_end,
        )
        await self.session.commit()
        return response

    async def capture_attendance_events(
        self,
        context: TenantContext,
        principal: Principal,
        live_class_id: uuid.UUID,
        payload: LiveAttendanceEventsRequest,
    ) -> LiveAttendanceEventsRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self._get_class_or_raise(tenant_id, live_class_id)
        events: list[LiveClassEvent] = []
        participants: list[LiveClassParticipant] = []
        for item in payload.events:
            occurred_at = (
                self._coerce_datetime(item.occurred_at)
                if item.occurred_at
                else datetime.now(UTC)
            )
            participant = await self._upsert_allowed_participant(
                tenant_id,
                live_class,
                user_id=item.user_id,
                student_id=item.student_id,
                employee_id=item.employee_id,
                role=item.participant_role,
                joined_at=occurred_at if item.event_type.endswith(".joined") else None,
            )
            if item.event_type == LiveClassEventType.PARTICIPANT_LEFT.value:
                if item.total_duration_seconds is not None:
                    participant.total_duration_seconds = item.total_duration_seconds
                elif participant.joined_at is not None:
                    participant.total_duration_seconds += self._duration_seconds(
                        participant.joined_at,
                        occurred_at,
                    )
                participant.left_at = occurred_at
                participant.join_status = LiveJoinStatus.COMPLETED.value
            event = await self._record_class_event(
                tenant_id,
                live_class.id,
                item.event_type,
                item.payload,
                participant_id=participant.id,
                occurred_at=occurred_at,
            )
            events.append(event)
            participants.append(participant)
        if payload.snapshot is not None:
            self.session.add(
                LiveClassAttendanceSnapshot(
                    tenant_id=tenant_id,
                    live_class_id=live_class.id,
                    participant_count=len(participants),
                    payload=payload.snapshot,
                )
            )
        await self.session.flush()
        for event in events:
            await self.session.refresh(event)
        for participant in participants:
            await self.session.refresh(participant)
        response = LiveAttendanceEventsRead(
            processed=len(events),
            events=[self._event_read(event) for event in events],
            participants=[self._participant_read(participant) for participant in participants],
        )
        await self.session.commit()
        await self._publish_event(
            "live.attendance_events.captured",
            context,
            principal,
            live_class.id,
        )
        return response

    async def add_recording(
        self,
        context: TenantContext,
        principal: Principal,
        live_class_id: uuid.UUID,
        payload: LiveClassRecordingCreate,
    ) -> LiveClassRecordingRead:
        tenant_id = self._require_tenant_id(context)
        live_class = await self._get_class_or_raise(tenant_id, live_class_id)
        recording = LiveClassRecording(
            tenant_id=tenant_id,
            live_class_id=live_class.id,
            provider_recording_id=payload.provider_recording_id,
            storage_key=payload.storage_key,
            playback_url=payload.playback_url,
            duration_seconds=payload.duration_seconds,
            status=payload.status.value,
            metadata_=payload.metadata,
        )
        await self.recordings.add(recording)
        await self._record_class_event(
            tenant_id,
            live_class.id,
            LiveClassEventType.RECORDING_ADDED.value,
            {"recording_id": str(recording.id)},
        )
        await self.session.refresh(recording)
        response = self._recording_read(recording)
        await self.session.commit()
        await self._publish_event(
            LiveClassEventType.RECORDING_ADDED.value,
            context,
            principal,
            recording.id,
        )
        return response

    async def _access_denial_reason(
        self,
        tenant_id: uuid.UUID,
        principal: Principal,
        live_class: LiveClass,
        payload: LiveAccessValidationRequest,
        now: datetime,
        join_start: datetime,
        join_end: datetime,
    ) -> str | None:
        if live_class.status not in JOINABLE_STATUSES:
            return "class_not_joinable"
        if now < join_start:
            return "join_window_not_open"
        if now > join_end:
            return "join_window_closed"
        existing = await self.participants.find_identity(
            tenant_id,
            live_class.id,
            user_id=self._validation_user_id(principal, payload),
            student_id=payload.student_id,
            employee_id=payload.employee_id,
        )
        if existing is None:
            active_count = await self.participants.active_count(tenant_id, live_class.id)
            if active_count >= live_class.capacity:
                return "class_capacity_full"
        if payload.student_id is not None:
            if not await self._student_in_batch(tenant_id, live_class.batch_id, payload.student_id):
                return "student_not_in_batch"
            return None
        if payload.employee_id is not None:
            return await self._employee_denial_reason(tenant_id, live_class, payload.employee_id)
        if (
            payload.participant_role == LiveParticipantRole.ADMIN
            and self._has_live_admin(principal)
        ):
            return None
        return "participant_not_allowed"

    async def _employee_denial_reason(
        self,
        tenant_id: uuid.UUID,
        live_class: LiveClass,
        employee_id: uuid.UUID,
    ) -> str | None:
        employee = await self._get_employee(tenant_id, employee_id)
        if employee is None:
            return "employee_not_found"
        if employee.id == live_class.instructor_id:
            return None
        if employee.employee_type in {EmployeeType.ADMIN.value, EmployeeType.MANAGER.value}:
            return None
        if await self._teacher_has_assignment(
            tenant_id,
            employee.id,
            course_id=live_class.course_id,
            batch_id=live_class.batch_id,
        ):
            return None
        return "employee_not_assigned"

    async def _upsert_allowed_participant(
        self,
        tenant_id: uuid.UUID,
        live_class: LiveClass,
        *,
        user_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        employee_id: uuid.UUID | None,
        role: LiveParticipantRole,
        joined_at: datetime | None,
    ) -> LiveClassParticipant:
        participant = await self.participants.find_identity(
            tenant_id,
            live_class.id,
            user_id=user_id,
            student_id=student_id,
            employee_id=employee_id,
        )
        if participant is None:
            participant = LiveClassParticipant(
                tenant_id=tenant_id,
                live_class_id=live_class.id,
                user_id=user_id,
                student_id=student_id,
                employee_id=employee_id,
                participant_role=role.value,
                join_status=LiveJoinStatus.ALLOWED.value,
                joined_at=joined_at,
            )
            await self.participants.add(participant)
            return participant
        participant.join_status = LiveJoinStatus.ALLOWED.value
        participant.participant_role = role.value
        if joined_at is not None:
            participant.joined_at = joined_at
            participant.left_at = None
        return participant

    async def _validate_optional_course_batch(
        self,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID | None,
        batch_id: uuid.UUID,
    ) -> None:
        if course_id is None:
            return
        course_exists = await self.session.scalar(
            select(Course.id).where(
                Course.tenant_id == tenant_id,
                Course.id == course_id,
                Course.deleted_at.is_(None),
            )
        )
        if course_exists is None:
            raise PrepSuiteError("course_not_found", "Course was not found.", status_code=404)
        mapped = await self.session.scalar(
            select(CourseBatch.id).where(
                CourseBatch.tenant_id == tenant_id,
                CourseBatch.course_id == course_id,
                CourseBatch.batch_id == batch_id,
                CourseBatch.status == CourseAssignmentStatus.ACTIVE.value,
            )
        )
        batch_course_id = await self.session.scalar(
            select(Batch.course_id).where(Batch.tenant_id == tenant_id, Batch.id == batch_id)
        )
        if mapped is None and batch_course_id != course_id:
            raise PrepSuiteError(
                "course_batch_not_assigned",
                "Course is not assigned to the selected batch.",
                status_code=422,
            )

    async def _validate_instructor(
        self,
        tenant_id: uuid.UUID,
        instructor_id: uuid.UUID,
        *,
        course_id: uuid.UUID | None,
        batch_id: uuid.UUID,
        admin_override: bool,
    ) -> None:
        employee = await self._get_employee(tenant_id, instructor_id)
        if employee is None:
            raise PrepSuiteError(
                "instructor_not_found",
                "Instructor was not found.",
                status_code=404,
            )
        if employee.employee_type != EmployeeType.TEACHER.value:
            raise PrepSuiteError(
                "instructor_not_teacher",
                "Instructor must be a teacher employee.",
                status_code=422,
            )
        if admin_override:
            return
        if await self._teacher_has_assignment(
            tenant_id,
            instructor_id,
            course_id=course_id,
            batch_id=batch_id,
        ):
            return
        raise PrepSuiteError(
            "instructor_not_assigned",
            "Teacher must be assigned to the course or batch.",
            status_code=422,
        )

    async def _teacher_has_assignment(
        self,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
        *,
        course_id: uuid.UUID | None,
        batch_id: uuid.UUID,
    ) -> bool:
        course_teacher = None
        if course_id is not None:
            course_teacher = await self.session.scalar(
                select(CourseTeacher.id).where(
                    CourseTeacher.tenant_id == tenant_id,
                    CourseTeacher.teacher_id == teacher_id,
                    CourseTeacher.course_id == course_id,
                    CourseTeacher.status == CourseAssignmentStatus.ACTIVE.value,
                )
            )
        assignment_filters = [TeacherAssignment.batch_id == batch_id]
        if course_id is not None:
            assignment_filters.append(TeacherAssignment.course_id == course_id)
        teacher_assignment = await self.session.scalar(
            select(TeacherAssignment.id).where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.teacher_id == teacher_id,
                TeacherAssignment.status == TeacherAssignmentStatus.ACTIVE.value,
                or_(*assignment_filters),
            )
        )
        return course_teacher is not None or teacher_assignment is not None

    async def _validate_batch(self, tenant_id: uuid.UUID, batch_id: uuid.UUID) -> None:
        exists = await self.session.scalar(
            select(Batch.id).where(
                Batch.tenant_id == tenant_id,
                Batch.id == batch_id,
                Batch.deleted_at.is_(None),
            )
        )
        if exists is None:
            raise PrepSuiteError("batch_not_found", "Batch was not found.", status_code=404)

    async def _get_employee(
        self,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> Employee | None:
        employee: Employee | None = await self.session.scalar(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.id == employee_id,
                Employee.status == EmployeeStatus.ACTIVE.value,
                Employee.deleted_at.is_(None),
            )
        )
        return employee

    async def _student_in_batch(
        self,
        tenant_id: uuid.UUID,
        batch_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> bool:
        student_exists = await self.session.scalar(
            select(Student.id).where(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
        )
        if student_exists is None:
            return False
        membership = await self.session.scalar(
            select(BatchStudent.id).where(
                BatchStudent.tenant_id == tenant_id,
                BatchStudent.batch_id == batch_id,
                BatchStudent.student_id == student_id,
                BatchStudent.status == "active",
            )
        )
        return membership is not None

    async def _generate_class_code(self, title: str) -> str:
        stem = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:24] or "class"
        for _ in range(8):
            suffix = secrets.token_urlsafe(8).replace("_", "").replace("-", "").lower()[:10]
            code = f"{stem}-{suffix}"
            if await self.live_classes.get_by_code(code) is None:
                return code
        raise PrepSuiteError(
            "live_class_code_generation_failed",
            "Could not generate a unique live class code.",
            status_code=500,
        )

    async def _get_class_or_raise(
        self,
        tenant_id: uuid.UUID,
        live_class_id: uuid.UUID,
    ) -> LiveClass:
        live_class = await self.live_classes.get_for_tenant(tenant_id, live_class_id)
        if live_class is None:
            raise PrepSuiteError(
                "live_class_not_found",
                "Live class was not found.",
                status_code=404,
            )
        return live_class

    async def _get_detail_or_raise(
        self,
        tenant_id: uuid.UUID,
        live_class_id: uuid.UUID,
    ) -> LiveClass:
        live_class = await self.live_classes.detail(tenant_id, live_class_id)
        if live_class is None:
            raise PrepSuiteError(
                "live_class_not_found",
                "Live class was not found.",
                status_code=404,
            )
        return live_class

    async def _record_class_event(
        self,
        tenant_id: uuid.UUID,
        live_class_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        participant_id: uuid.UUID | None = None,
        occurred_at: datetime | None = None,
    ) -> LiveClassEvent:
        event = LiveClassEvent(
            tenant_id=tenant_id,
            live_class_id=live_class_id,
            participant_id=participant_id,
            event_type=event_type,
            occurred_at=occurred_at or datetime.now(UTC),
            payload=payload,
        )
        await self.events.add(event)
        return event

    def _join_window(self, live_class: LiveClass) -> tuple[datetime, datetime]:
        starts_at = self._coerce_datetime(live_class.starts_at)
        ends_at = self._coerce_datetime(live_class.ends_at)
        return (
            starts_at - timedelta(minutes=live_class.join_before_minutes),
            ends_at + timedelta(minutes=live_class.join_after_minutes),
        )

    def _assert_live_class_time_window(self, starts_at: datetime, ends_at: datetime) -> None:
        if self._coerce_datetime(ends_at) <= self._coerce_datetime(starts_at):
            raise PrepSuiteError(
                "invalid_live_class_window",
                "Live class ends_at must be after starts_at.",
                status_code=422,
            )

    def _assert_admin_override_allowed(self, principal: Principal, admin_override: bool) -> None:
        if admin_override and not self._has_live_admin(principal):
            raise PrepSuiteError(
                "permission_denied",
                "Admin override requires live class management permission.",
                status_code=403,
                details={"permission": "preplive.class.manage"},
            )

    def _has_live_admin(self, principal: Principal) -> bool:
        return "preplive.class.manage" in principal.permissions

    def _infer_role(
        self,
        live_class: LiveClass,
        payload: LiveAccessValidationRequest,
    ) -> LiveParticipantRole:
        if payload.student_id is not None:
            return LiveParticipantRole.STUDENT
        if payload.employee_id == live_class.instructor_id:
            return LiveParticipantRole.INSTRUCTOR
        if payload.employee_id is not None:
            return LiveParticipantRole.CO_INSTRUCTOR
        return LiveParticipantRole.ADMIN

    def _validation_user_id(
        self,
        principal: Principal,
        payload: LiveAccessValidationRequest,
    ) -> uuid.UUID | None:
        if payload.student_id is not None or payload.employee_id is not None:
            return payload.user_id
        return payload.user_id or principal.user_id

    def _duration_seconds(self, started_at: datetime, ended_at: datetime) -> int:
        return max(
            0,
            int(
                (
                    self._coerce_datetime(ended_at)
                    - self._coerce_datetime(started_at)
                ).total_seconds()
            ),
        )

    def _coerce_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def _live_link(self, class_code: str) -> str:
        return f"{LIVE_LINK_BASE_URL}/{class_code}"

    def _class_read(self, live_class: LiveClass) -> LiveClassRead:
        return LiveClassRead.model_validate(live_class)

    def _participant_read(self, participant: LiveClassParticipant) -> LiveClassParticipantRead:
        return LiveClassParticipantRead.model_validate(participant)

    def _recording_read(self, recording: LiveClassRecording) -> LiveClassRecordingRead:
        return LiveClassRecordingRead.model_validate(recording)

    def _event_read(self, event: LiveClassEvent) -> LiveClassEventRead:
        return LiveClassEventRead.model_validate(event)

    def _class_detail_read(self, live_class: LiveClass) -> LiveClassDetailRead:
        return LiveClassDetailRead(
            live_class=self._class_read(live_class),
            participants=[
                self._participant_read(participant)
                for participant in sorted(live_class.participants, key=lambda item: item.created_at)
            ],
            recordings=[
                self._recording_read(recording)
                for recording in sorted(live_class.recordings, key=lambda item: item.created_at)
            ],
            events=[
                self._event_read(event)
                for event in sorted(live_class.events, key=lambda item: item.occurred_at)
            ],
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
