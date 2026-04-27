from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import TenantContext
from app.modules.access.models import User
from app.modules.people.enums import (
    DepartmentStatus,
    EmployeeStatus,
    EmployeeType,
    TeacherAssignmentStatus,
)
from app.modules.people.models import (
    Department,
    Employee,
    EmployeeDocument,
    EmployeeNote,
    EmployeeProfile,
    EmployeeStatusHistory,
    TeacherAssignment,
)
from app.modules.people.repository import (
    DepartmentRepository,
    EmployeeDocumentRepository,
    EmployeeNoteRepository,
    EmployeeProfileRepository,
    EmployeeRepository,
    EmployeeStatusHistoryRepository,
    TeacherAssignmentRepository,
)
from app.modules.people.schemas import (
    DepartmentCreate,
    EmployeeCreate,
    EmployeeDocumentCreate,
    EmployeeNoteCreate,
    EmployeePage,
    EmployeeProfileUpsert,
    EmployeeRead,
    EmployeeTimelineEvent,
    EmployeeUpdate,
    TeacherAssignmentCreate,
    TeacherAssignmentRead,
    TeacherWorkloadRead,
)
from app.modules.students.models import Batch


class PrepPeopleService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.departments = DepartmentRepository(session)
        self.employees = EmployeeRepository(session)
        self.profiles = EmployeeProfileRepository(session)
        self.documents = EmployeeDocumentRepository(session)
        self.notes = EmployeeNoteRepository(session)
        self.status_history = EmployeeStatusHistoryRepository(session)
        self.assignments = TeacherAssignmentRepository(session)

    async def list_employees(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor: str | None,
        status: EmployeeStatus | None,
        employee_type: EmployeeType | None,
        department_id: uuid.UUID | None,
        search: str | None,
        sort: str,
    ) -> EmployeePage:
        tenant_id = self._require_tenant_id(context)
        result = await self.employees.list_for_tenant(
            tenant_id,
            limit=limit,
            cursor=cursor,
            status=status.value if status else None,
            employee_type=employee_type.value if employee_type else None,
            department_id=department_id,
            search=search,
            sort=sort,
        )
        return EmployeePage(
            items=[EmployeeRead.model_validate(item) for item in result.items],
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    async def create_employee(
        self,
        context: TenantContext,
        principal: Principal,
        payload: EmployeeCreate,
    ) -> Employee:
        tenant_id = self._require_tenant_id(context)
        await self._validate_user_link(tenant_id, payload.user_id)
        await self._validate_department(tenant_id, payload.department_id)
        data = payload.model_dump(mode="python", exclude={"profile"})
        employee = Employee(tenant_id=tenant_id, **data)
        self.session.add(employee)
        try:
            await self.session.flush()
            if payload.profile is not None:
                await self._upsert_profile(tenant_id, employee.id, payload.profile)
            await self._append_status_history(
                employee,
                from_status=None,
                to_status=employee.status,
                reason="employee created",
                principal=principal,
            )
            await self.session.refresh(employee)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "employee_conflict",
                "Employee code or linked user already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("employee.created", context, principal, employee.id)
        return employee

    async def get_employee(self, context: TenantContext, employee_id: uuid.UUID) -> Employee:
        tenant_id = self._require_tenant_id(context)
        employee = await self.employees.get_for_tenant(tenant_id, employee_id)
        if employee is None:
            raise PrepSuiteError("employee_not_found", "Employee was not found.", status_code=404)
        return employee

    async def update_employee(
        self,
        context: TenantContext,
        principal: Principal,
        employee_id: uuid.UUID,
        payload: EmployeeUpdate,
    ) -> Employee:
        tenant_id = self._require_tenant_id(context)
        employee = await self.get_employee(context, employee_id)
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        profile_payload = update_data.pop("profile", None)
        status_reason = update_data.pop("status_change_reason", None)
        if "user_id" in update_data:
            await self._validate_user_link(tenant_id, update_data["user_id"])
        if "department_id" in update_data:
            await self._validate_department(tenant_id, update_data["department_id"])
        previous_status = employee.status
        for field, value in update_data.items():
            setattr(employee, field, value)
        if "status" in update_data and update_data["status"] != previous_status:
            await self._append_status_history(
                employee,
                from_status=previous_status,
                to_status=update_data["status"],
                reason=status_reason,
                principal=principal,
            )
        if profile_payload is not None:
            await self._upsert_profile(tenant_id, employee.id, profile_payload)
        try:
            await self.session.flush()
            await self.session.refresh(employee)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "employee_conflict",
                "Employee code or linked user already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("employee.updated", context, principal, employee.id)
        return employee

    async def get_profile(self, context: TenantContext, employee_id: uuid.UUID) -> dict[str, Any]:
        tenant_id = self._require_tenant_id(context)
        employee = await self.employees.profile(tenant_id, employee_id)
        if employee is None:
            raise PrepSuiteError("employee_not_found", "Employee was not found.", status_code=404)
        return {
            "employee": employee,
            "profile": employee.profile,
            "department": employee.department,
            "documents": sorted(employee.documents, key=lambda item: item.created_at, reverse=True),
            "notes": sorted(employee.notes, key=lambda item: item.created_at, reverse=True),
            "status_history": sorted(
                employee.status_history,
                key=lambda item: item.created_at,
                reverse=True,
            ),
            "teacher_assignments": sorted(
                employee.assignments,
                key=lambda item: item.created_at,
                reverse=True,
            ),
        }

    async def timeline(
        self,
        context: TenantContext,
        employee_id: uuid.UUID,
    ) -> list[EmployeeTimelineEvent]:
        profile = await self.get_profile(context, employee_id)
        employee: Employee = profile["employee"]
        events = [
            EmployeeTimelineEvent(
                event_type="employee.created",
                event_id=employee.id,
                occurred_at=employee.created_at,
                title="Employee created",
                details={"employee_code": employee.employee_code},
            )
        ]
        for history in profile["status_history"]:
            events.append(
                EmployeeTimelineEvent(
                    event_type="employee.status_changed",
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
        for assignment in profile["teacher_assignments"]:
            events.append(
                EmployeeTimelineEvent(
                    event_type="teacher.assignment.created",
                    event_id=assignment.id,
                    occurred_at=assignment.created_at,
                    title="Teacher assignment created",
                    details={
                        "course_id": str(assignment.course_id) if assignment.course_id else None,
                        "batch_id": str(assignment.batch_id) if assignment.batch_id else None,
                        "status": assignment.status,
                    },
                )
            )
        for note in profile["notes"]:
            events.append(
                EmployeeTimelineEvent(
                    event_type="employee.note_added",
                    event_id=note.id,
                    occurred_at=note.created_at,
                    title="Note added",
                    details={"note_type": note.note_type, "visibility": note.visibility},
                )
            )
        for document in profile["documents"]:
            events.append(
                EmployeeTimelineEvent(
                    event_type="employee.document_added",
                    event_id=document.id,
                    occurred_at=document.created_at,
                    title="Document metadata added",
                    details={"document_type": document.document_type, "title": document.title},
                )
            )
        return sorted(events, key=lambda event: event.occurred_at, reverse=True)

    async def create_department(
        self,
        context: TenantContext,
        principal: Principal,
        payload: DepartmentCreate,
    ) -> Department:
        tenant_id = self._require_tenant_id(context)
        department = Department(tenant_id=tenant_id, **payload.model_dump(mode="python"))
        try:
            await self.departments.add(department)
            await self.session.refresh(department)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "department_conflict",
                "Department code already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("department.created", context, principal, department.id)
        return department

    async def list_departments(
        self,
        context: TenantContext,
        *,
        status: DepartmentStatus | None,
        search: str | None,
    ) -> list[Department]:
        tenant_id = self._require_tenant_id(context)
        return list(
            await self.departments.list_for_tenant(
                tenant_id,
                status=status.value if status else None,
                search=search,
            )
        )

    async def create_teacher_assignment(
        self,
        context: TenantContext,
        principal: Principal,
        payload: TeacherAssignmentCreate,
    ) -> TeacherAssignment:
        tenant_id = self._require_tenant_id(context)
        teacher = await self.get_employee(context, payload.teacher_id)
        if teacher.employee_type != EmployeeType.TEACHER.value:
            raise PrepSuiteError(
                "employee_not_teacher",
                "Only teacher employees can receive teacher assignments.",
                status_code=422,
                details={"employee_id": str(teacher.id)},
            )
        await self._validate_batch(tenant_id, payload.batch_id)
        assignment = TeacherAssignment(tenant_id=tenant_id, **payload.model_dump(mode="python"))
        await self.assignments.add(assignment)
        await self.session.refresh(assignment)
        await self.session.commit()
        await self._publish_event("teacher.assignment.created", context, principal, assignment.id)
        return assignment

    async def teacher_workload(
        self,
        context: TenantContext,
        teacher_id: uuid.UUID,
    ) -> TeacherWorkloadRead:
        tenant_id = self._require_tenant_id(context)
        teacher = await self.get_employee(context, teacher_id)
        if teacher.employee_type != EmployeeType.TEACHER.value:
            raise PrepSuiteError(
                "employee_not_teacher",
                "Only teacher employees have a teacher workload summary.",
                status_code=422,
                details={"employee_id": str(teacher.id)},
            )
        assignments = list(await self.assignments.list_for_teacher(tenant_id, teacher.id))
        active_assignments = [
            item for item in assignments if item.status == TeacherAssignmentStatus.ACTIVE.value
        ]
        return TeacherWorkloadRead(
            teacher_id=teacher.id,
            active_assignment_count=len(active_assignments),
            course_count=len({item.course_id for item in active_assignments if item.course_id}),
            batch_count=len({item.batch_id for item in active_assignments if item.batch_id}),
            assignments=[TeacherAssignmentRead.model_validate(item) for item in assignments],
        )

    async def add_note(
        self,
        context: TenantContext,
        principal: Principal,
        employee_id: uuid.UUID,
        payload: EmployeeNoteCreate,
    ) -> EmployeeNote:
        tenant_id = self._require_tenant_id(context)
        employee = await self.get_employee(context, employee_id)
        note = EmployeeNote(
            tenant_id=tenant_id,
            employee_id=employee.id,
            author_user_id=principal.user_id,
            **payload.model_dump(mode="python"),
        )
        await self.notes.add(note)
        await self.session.refresh(note)
        await self.session.commit()
        await self._publish_event("employee.note_added", context, principal, employee.id)
        return note

    async def add_document(
        self,
        context: TenantContext,
        principal: Principal,
        employee_id: uuid.UUID,
        payload: EmployeeDocumentCreate,
    ) -> EmployeeDocument:
        tenant_id = self._require_tenant_id(context)
        employee = await self.get_employee(context, employee_id)
        document_data = payload.model_dump(mode="python")
        metadata = document_data.pop("metadata", {})
        document = EmployeeDocument(
            tenant_id=tenant_id,
            employee_id=employee.id,
            uploaded_by=principal.user_id,
            metadata_=metadata,
            **document_data,
        )
        await self.documents.add(document)
        await self.session.refresh(document)
        await self.session.commit()
        await self._publish_event("employee.document_added", context, principal, employee.id)
        return document

    async def _upsert_profile(
        self,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        payload: EmployeeProfileUpsert | dict[str, Any],
    ) -> EmployeeProfile:
        profile = await self.profiles.get_by_employee(tenant_id, employee_id)
        profile_data = (
            payload.model_dump(mode="python")
            if isinstance(payload, EmployeeProfileUpsert)
            else payload
        )
        if profile is None:
            profile = EmployeeProfile(
                tenant_id=tenant_id,
                employee_id=employee_id,
                **profile_data,
            )
            await self.profiles.add(profile)
            return profile
        for field, value in profile_data.items():
            setattr(profile, field, value)
        await self.session.flush()
        return profile

    async def _append_status_history(
        self,
        employee: Employee,
        *,
        from_status: str | None,
        to_status: str,
        reason: str | None,
        principal: Principal,
    ) -> None:
        history = EmployeeStatusHistory(
            tenant_id=employee.tenant_id,
            employee_id=employee.id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            changed_by=principal.user_id,
        )
        await self.status_history.add(history)

    async def _validate_department(
        self,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID | None,
    ) -> None:
        if department_id is None:
            return
        department = await self.departments.get_for_tenant(tenant_id, department_id)
        if department is None:
            raise PrepSuiteError(
                "department_not_found",
                "Department was not found.",
                status_code=404,
            )

    async def _validate_user_link(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
        if user_id is None:
            return
        statement = select(User.id).where(
            User.tenant_id == tenant_id,
            User.id == user_id,
            User.deleted_at.is_(None),
        )
        if await self.session.scalar(statement) is None:
            raise PrepSuiteError(
                "user_not_found",
                "Linked PrepAccess user was not found for this tenant.",
                status_code=404,
            )

    async def _validate_batch(self, tenant_id: uuid.UUID, batch_id: uuid.UUID | None) -> None:
        if batch_id is None:
            return
        statement = select(Batch.id).where(
            Batch.tenant_id == tenant_id,
            Batch.id == batch_id,
            Batch.deleted_at.is_(None),
        )
        if await self.session.scalar(statement) is None:
            raise PrepSuiteError("batch_not_found", "Batch was not found.", status_code=404)

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
