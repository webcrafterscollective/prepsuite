from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import TenantContext
from app.modules.students.enums import BatchStatus, BatchStudentStatus, StudentStatus
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
from app.modules.students.repository import (
    BatchRepository,
    BatchStudentRepository,
    GuardianRepository,
    StudentDocumentRepository,
    StudentEnrollmentRepository,
    StudentGuardianRepository,
    StudentNoteRepository,
    StudentRepository,
    StudentStatusHistoryRepository,
)
from app.modules.students.schemas import (
    BatchCreate,
    BatchUpdate,
    GuardianCreate,
    StudentBulkImportError,
    StudentBulkImportItem,
    StudentBulkImportRequest,
    StudentBulkImportResponse,
    StudentCreate,
    StudentDocumentCreate,
    StudentEnrollmentCreate,
    StudentNoteCreate,
    StudentPage,
    StudentRead,
    StudentTimelineEvent,
    StudentUpdate,
)


class PrepStudentsService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.students = StudentRepository(session)
        self.guardians = GuardianRepository(session)
        self.student_guardians = StudentGuardianRepository(session)
        self.batches = BatchRepository(session)
        self.batch_students = BatchStudentRepository(session)
        self.enrollments = StudentEnrollmentRepository(session)
        self.notes = StudentNoteRepository(session)
        self.documents = StudentDocumentRepository(session)
        self.status_history = StudentStatusHistoryRepository(session)

    async def list_students(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor: str | None,
        status: StudentStatus | None,
        search: str | None,
        batch_id: uuid.UUID | None,
        sort: str,
    ) -> StudentPage:
        tenant_id = self._require_tenant_id(context)
        result = await self.students.list_for_tenant(
            tenant_id,
            limit=limit,
            cursor=cursor,
            status=status.value if status else None,
            search=search,
            batch_id=batch_id,
            sort=sort,
        )
        return StudentPage(
            items=[StudentRead.model_validate(item) for item in result.items],
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    async def create_student(
        self,
        context: TenantContext,
        principal: Principal,
        payload: StudentCreate,
    ) -> Student:
        tenant_id = self._require_tenant_id(context)
        student = Student(tenant_id=tenant_id, **payload.model_dump(mode="python"))
        self.session.add(student)
        try:
            await self.session.flush()
            await self._append_status_history(
                student,
                from_status=None,
                to_status=student.status,
                reason="student created",
                principal=principal,
            )
            await self.session.refresh(student)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "student_conflict",
                "Student admission number already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("student.created", context, principal, student.id)
        return student

    async def bulk_import_students(
        self,
        context: TenantContext,
        principal: Principal,
        payload: StudentBulkImportRequest,
    ) -> StudentBulkImportResponse:
        created: list[Student] = []
        errors: list[StudentBulkImportError] = []
        seen_admission_numbers: set[str] = set()
        for index, item in enumerate(payload.students):
            if item.admission_no in seen_admission_numbers:
                errors.append(
                    StudentBulkImportError(
                        index=index,
                        admission_no=item.admission_no,
                        code="duplicate_in_payload",
                        message="Admission number appears more than once in the import payload.",
                    )
                )
                continue
            seen_admission_numbers.add(item.admission_no)
            try:
                student = await self._create_student_without_commit(context, principal, item)
                created.append(student)
            except PrepSuiteError as exc:
                errors.append(
                    StudentBulkImportError(
                        index=index,
                        admission_no=item.admission_no,
                        code=exc.code,
                        message=exc.message,
                    )
                )
        await self.session.commit()
        for student in created:
            await self._publish_event("student.created", context, principal, student.id)
        return StudentBulkImportResponse(
            created=[StudentRead.model_validate(student) for student in created],
            errors=errors,
        )

    async def get_student(self, context: TenantContext, student_id: uuid.UUID) -> Student:
        tenant_id = self._require_tenant_id(context)
        student = await self.students.get_for_tenant(tenant_id, student_id)
        if student is None:
            raise PrepSuiteError("student_not_found", "Student was not found.", status_code=404)
        return student

    async def update_student(
        self,
        context: TenantContext,
        principal: Principal,
        student_id: uuid.UUID,
        payload: StudentUpdate,
    ) -> Student:
        student = await self.get_student(context, student_id)
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        status_reason = update_data.pop("status_change_reason", None)
        previous_status = student.status
        for field, value in update_data.items():
            setattr(student, field, value)
        if "status" in update_data and update_data["status"] != previous_status:
            await self._append_status_history(
                student,
                from_status=previous_status,
                to_status=update_data["status"],
                reason=status_reason,
                principal=principal,
            )
        try:
            await self.session.flush()
            await self.session.refresh(student)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "student_conflict",
                "Student admission number already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("student.updated", context, principal, student.id)
        return student

    async def delete_student(
        self,
        context: TenantContext,
        principal: Principal,
        student_id: uuid.UUID,
    ) -> None:
        student = await self.get_student(context, student_id)
        student.deleted_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()
        await self._publish_event("student.deleted", context, principal, student.id)

    async def get_profile(self, context: TenantContext, student_id: uuid.UUID) -> dict[str, Any]:
        tenant_id = self._require_tenant_id(context)
        student = await self.students.profile(tenant_id, student_id)
        if student is None:
            raise PrepSuiteError("student_not_found", "Student was not found.", status_code=404)
        return {
            "student": student,
            "guardians": sorted(student.guardians, key=lambda item: not item.is_primary),
            "batches": sorted(student.batch_links, key=lambda item: item.joined_at, reverse=True),
            "enrollments": sorted(
                student.enrollments,
                key=lambda item: item.enrolled_at,
                reverse=True,
            ),
            "notes": sorted(student.notes, key=lambda item: item.created_at, reverse=True),
            "documents": sorted(student.documents, key=lambda item: item.created_at, reverse=True),
            "status_history": sorted(
                student.status_history,
                key=lambda item: item.created_at,
                reverse=True,
            ),
        }

    async def timeline(
        self,
        context: TenantContext,
        student_id: uuid.UUID,
    ) -> list[StudentTimelineEvent]:
        profile = await self.get_profile(context, student_id)
        events: list[StudentTimelineEvent] = []
        student: Student = profile["student"]
        events.append(
            StudentTimelineEvent(
                event_type="student.created",
                event_id=student.id,
                occurred_at=student.created_at,
                title="Student created",
                details={"admission_no": student.admission_no},
            )
        )
        for history in profile["status_history"]:
            events.append(
                StudentTimelineEvent(
                    event_type="student.status_changed",
                    event_id=history.id,
                    occurred_at=history.created_at,
                    title=f"Status changed to {history.to_status}",
                    details={
                        "from_status": history.from_status,
                        "to_status": history.to_status,
                        "reason": history.reason,
                    },
                )
            )
        for link in profile["batches"]:
            events.append(
                StudentTimelineEvent(
                    event_type="student.batch_membership",
                    event_id=link.id,
                    occurred_at=link.joined_at,
                    title="Batch membership updated",
                    details={"batch_id": str(link.batch_id), "status": link.status},
                )
            )
        for enrollment in profile["enrollments"]:
            events.append(
                StudentTimelineEvent(
                    event_type="student.enrolled",
                    event_id=enrollment.id,
                    occurred_at=enrollment.enrolled_at,
                    title="Course enrollment created",
                    details={"course_id": str(enrollment.course_id), "status": enrollment.status},
                )
            )
        for note in profile["notes"]:
            events.append(
                StudentTimelineEvent(
                    event_type="student.note_added",
                    event_id=note.id,
                    occurred_at=note.created_at,
                    title="Note added",
                    details={"note_type": note.note_type, "visibility": note.visibility},
                )
            )
        return sorted(events, key=lambda event: event.occurred_at, reverse=True)

    async def add_guardian(
        self,
        context: TenantContext,
        principal: Principal,
        student_id: uuid.UUID,
        payload: GuardianCreate,
    ) -> StudentGuardian:
        tenant_id = self._require_tenant_id(context)
        student = await self.get_student(context, student_id)
        guardian_data = payload.model_dump(
            exclude={"is_primary", "can_pickup", "emergency_contact"},
            mode="python",
        )
        metadata = guardian_data.pop("metadata", {})
        guardian = Guardian(tenant_id=tenant_id, metadata_=metadata, **guardian_data)
        self.session.add(guardian)
        await self.session.flush()
        link = StudentGuardian(
            tenant_id=tenant_id,
            student_id=student.id,
            guardian_id=guardian.id,
            relationship_type=payload.relationship_type,
            is_primary=payload.is_primary,
            can_pickup=payload.can_pickup,
            emergency_contact=payload.emergency_contact,
        )
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link, attribute_names=["guardian"])
        await self.session.commit()
        await self._publish_event("student.guardian_added", context, principal, student.id)
        return link

    async def add_note(
        self,
        context: TenantContext,
        principal: Principal,
        student_id: uuid.UUID,
        payload: StudentNoteCreate,
    ) -> StudentNote:
        tenant_id = self._require_tenant_id(context)
        student = await self.get_student(context, student_id)
        note = StudentNote(
            tenant_id=tenant_id,
            student_id=student.id,
            author_user_id=principal.user_id,
            **payload.model_dump(mode="python"),
        )
        await self.notes.add(note)
        await self.session.refresh(note)
        await self.session.commit()
        await self._publish_event("student.note_added", context, principal, student.id)
        return note

    async def add_document(
        self,
        context: TenantContext,
        principal: Principal,
        student_id: uuid.UUID,
        payload: StudentDocumentCreate,
    ) -> StudentDocument:
        tenant_id = self._require_tenant_id(context)
        student = await self.get_student(context, student_id)
        document_data = payload.model_dump(mode="python")
        metadata = document_data.pop("metadata", {})
        document = StudentDocument(
            tenant_id=tenant_id,
            student_id=student.id,
            uploaded_by=principal.user_id,
            metadata_=metadata,
            **document_data,
        )
        await self.documents.add(document)
        await self.session.refresh(document)
        await self.session.commit()
        await self._publish_event("student.document_added", context, principal, student.id)
        return document

    async def enroll_student(
        self,
        context: TenantContext,
        principal: Principal,
        student_id: uuid.UUID,
        payload: StudentEnrollmentCreate,
    ) -> StudentEnrollment:
        tenant_id = self._require_tenant_id(context)
        student = await self.get_student(context, student_id)
        if payload.batch_id is not None:
            await self._get_batch_or_raise(tenant_id, payload.batch_id)
        enrollment = StudentEnrollment(
            tenant_id=tenant_id,
            student_id=student.id,
            **payload.model_dump(mode="python"),
        )
        await self.enrollments.add(enrollment)
        await self.session.refresh(enrollment)
        await self.session.commit()
        await self._publish_event("student.enrolled", context, principal, student.id)
        return enrollment

    async def create_batch(
        self,
        context: TenantContext,
        principal: Principal,
        payload: BatchCreate,
    ) -> Batch:
        tenant_id = self._require_tenant_id(context)
        batch = Batch(tenant_id=tenant_id, **payload.model_dump(mode="python"))
        try:
            await self.batches.add(batch)
            await self.session.refresh(batch)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "batch_conflict",
                "Batch code already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("batch.created", context, principal, batch.id)
        return batch

    async def list_batches(
        self,
        context: TenantContext,
        *,
        status: BatchStatus | None,
        search: str | None,
    ) -> list[Batch]:
        tenant_id = self._require_tenant_id(context)
        status_value = status.value if status else None
        return list(
            await self.batches.list_for_tenant(
                tenant_id,
                status=status_value,
                search=search,
            )
        )

    async def get_batch(self, context: TenantContext, batch_id: uuid.UUID) -> Batch:
        tenant_id = self._require_tenant_id(context)
        return await self._get_batch_or_raise(tenant_id, batch_id)

    async def update_batch(
        self,
        context: TenantContext,
        principal: Principal,
        batch_id: uuid.UUID,
        payload: BatchUpdate,
    ) -> Batch:
        tenant_id = self._require_tenant_id(context)
        batch = await self._get_batch_or_raise(tenant_id, batch_id)
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        start_date = update_data.get("start_date", batch.start_date)
        end_date = update_data.get("end_date", batch.end_date)
        if end_date is not None and end_date < start_date:
            raise PrepSuiteError(
                "batch_date_invalid",
                "Batch end_date must be on or after start_date.",
                status_code=422,
            )
        new_capacity = update_data.get("capacity", batch.capacity)
        if new_capacity is not None:
            active_count = await self.batch_students.active_count(tenant_id, batch.id)
            if active_count > new_capacity:
                raise PrepSuiteError(
                    "batch_capacity_below_membership",
                    "Batch capacity cannot be lower than active student membership.",
                    status_code=409,
                    details={"active_students": active_count, "capacity": new_capacity},
                )
        for field, value in update_data.items():
            setattr(batch, field, value)
        await self.session.flush()
        await self.session.refresh(batch)
        await self.session.commit()
        await self._publish_event("batch.updated", context, principal, batch.id)
        return batch

    async def assign_student_to_batch(
        self,
        context: TenantContext,
        principal: Principal,
        batch_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> BatchStudent:
        tenant_id = self._require_tenant_id(context)
        batch = await self._get_batch_or_raise(tenant_id, batch_id)
        student = await self.get_student(context, student_id)
        active_count = await self.batch_students.active_count(tenant_id, batch.id)
        existing = await self.batch_students.get_membership(tenant_id, batch.id, student.id)
        if existing is not None and existing.status == BatchStudentStatus.ACTIVE.value:
            return existing
        if batch.capacity is not None and active_count >= batch.capacity:
            raise PrepSuiteError(
                "batch_capacity_exceeded",
                "Batch capacity has been reached.",
                status_code=409,
                details={"batch_id": str(batch.id), "capacity": batch.capacity},
            )
        if existing is None:
            membership = BatchStudent(
                tenant_id=tenant_id,
                batch_id=batch.id,
                student_id=student.id,
                status=BatchStudentStatus.ACTIVE.value,
            )
            await self.batch_students.add(membership)
        else:
            existing.status = BatchStudentStatus.ACTIVE.value
            existing.left_at = None
            existing.joined_at = datetime.now(UTC)
            membership = existing
        await self.session.flush()
        await self.session.refresh(membership)
        await self.session.commit()
        await self._publish_event("student.assigned_to_batch", context, principal, student.id)
        return membership

    async def remove_student_from_batch(
        self,
        context: TenantContext,
        principal: Principal,
        batch_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> None:
        tenant_id = self._require_tenant_id(context)
        await self._get_batch_or_raise(tenant_id, batch_id)
        await self.get_student(context, student_id)
        membership = await self.batch_students.get_membership(tenant_id, batch_id, student_id)
        if membership is None or membership.status != BatchStudentStatus.ACTIVE.value:
            raise PrepSuiteError(
                "batch_membership_not_found",
                "Student is not active in this batch.",
                status_code=404,
            )
        membership.status = BatchStudentStatus.REMOVED.value
        membership.left_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()
        await self._publish_event("student.removed_from_batch", context, principal, student_id)

    async def _create_student_without_commit(
        self,
        context: TenantContext,
        principal: Principal,
        payload: StudentBulkImportItem,
    ) -> Student:
        tenant_id = self._require_tenant_id(context)
        existing = await self.students.get_by_admission_no(tenant_id, payload.admission_no)
        if existing is not None:
            raise PrepSuiteError(
                "student_conflict",
                "Student admission number already exists for this tenant.",
                status_code=409,
            )
        student = Student(tenant_id=tenant_id, **payload.model_dump(mode="python"))
        self.session.add(student)
        await self.session.flush()
        await self._append_status_history(
            student,
            from_status=None,
            to_status=student.status,
            reason="student imported",
            principal=principal,
        )
        await self.session.refresh(student)
        return student

    async def _get_batch_or_raise(self, tenant_id: uuid.UUID, batch_id: uuid.UUID) -> Batch:
        batch = await self.batches.get_for_tenant(tenant_id, batch_id)
        if batch is None:
            raise PrepSuiteError("batch_not_found", "Batch was not found.", status_code=404)
        return batch

    async def _append_status_history(
        self,
        student: Student,
        *,
        from_status: str | None,
        to_status: str,
        reason: str | None,
        principal: Principal,
    ) -> None:
        history = StudentStatusHistory(
            tenant_id=student.tenant_id,
            student_id=student.id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            changed_by=principal.user_id,
        )
        await self.status_history.add(history)

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
