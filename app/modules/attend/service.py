from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import TenantContext
from app.modules.attend.enums import (
    AttendanceCorrectionStatus,
    AttendanceCorrectionTarget,
    EmployeeAttendanceStatus,
    StudentAttendanceSessionStatus,
    StudentAttendanceStatus,
)
from app.modules.attend.models import (
    AttendanceCorrectionRequest,
    EmployeeAttendanceRecord,
    StudentAttendanceRecord,
    StudentAttendanceSession,
)
from app.modules.attend.repository import (
    AttendanceCorrectionRequestRepository,
    EmployeeAttendanceRecordRepository,
    StudentAttendanceRecordRepository,
    StudentAttendanceSessionRepository,
)
from app.modules.attend.schemas import (
    AttendanceCorrectionApproveRequest,
    AttendanceCorrectionCreate,
    AttendanceCorrectionRead,
    EmployeeAttendanceRecordRead,
    EmployeeAttendanceSummaryItem,
    EmployeeAttendanceSummaryRead,
    EmployeeCheckInRequest,
    EmployeeCheckOutRequest,
    StudentAttendanceRecordRead,
    StudentAttendanceRecordsRequest,
    StudentAttendanceRecordUpdate,
    StudentAttendanceSessionCreate,
    StudentAttendanceSessionRead,
    StudentAttendanceSummaryItem,
    StudentAttendanceSummaryRead,
)
from app.modules.people.models import Employee
from app.modules.students.models import Batch, BatchStudent, Student

LOCKED_SESSION_STATUSES = {
    StudentAttendanceSessionStatus.LOCKED.value,
    StudentAttendanceSessionStatus.CANCELLED.value,
}


class PrepAttendService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.student_sessions = StudentAttendanceSessionRepository(session)
        self.student_records = StudentAttendanceRecordRepository(session)
        self.employee_records = EmployeeAttendanceRecordRepository(session)
        self.corrections = AttendanceCorrectionRequestRepository(session)

    async def create_student_session(
        self,
        context: TenantContext,
        principal: Principal,
        payload: StudentAttendanceSessionCreate,
    ) -> StudentAttendanceSessionRead:
        tenant_id = self._require_tenant_id(context)
        await self._validate_batch(tenant_id, payload.batch_id)
        attendance_session = StudentAttendanceSession(
            tenant_id=tenant_id,
            batch_id=payload.batch_id,
            course_id=payload.course_id,
            live_class_id=payload.live_class_id,
            date=payload.date,
            marked_by=principal.user_id,
            status=payload.status.value,
            metadata_=payload.metadata,
        )
        await self.student_sessions.add(attendance_session)
        await self.session.refresh(attendance_session)
        response = self._student_session_read(attendance_session)
        await self.session.commit()
        await self._publish_event(
            "attendance.student_session.created",
            context,
            principal,
            attendance_session.id,
        )
        return response

    async def mark_student_records(
        self,
        context: TenantContext,
        principal: Principal,
        session_id: uuid.UUID,
        payload: StudentAttendanceRecordsRequest,
    ) -> list[StudentAttendanceRecordRead]:
        tenant_id = self._require_tenant_id(context)
        attendance_session = await self._get_student_session_or_raise(tenant_id, session_id)
        self._assert_session_writable(attendance_session)
        records: list[StudentAttendanceRecord] = []
        try:
            for item in payload.records:
                await self._validate_student_membership(
                    tenant_id,
                    attendance_session.batch_id,
                    item.student_id,
                )
                existing = await self.student_records.get_for_session_student(
                    tenant_id,
                    attendance_session.id,
                    item.student_id,
                )
                if existing is None:
                    record = StudentAttendanceRecord(
                        tenant_id=tenant_id,
                        session_id=attendance_session.id,
                        student_id=item.student_id,
                        status=item.status.value,
                        marked_by=principal.user_id,
                        remarks=item.remarks,
                        metadata_=item.metadata,
                    )
                    await self.student_records.add(record)
                    records.append(record)
                else:
                    existing.status = item.status.value
                    existing.marked_by = principal.user_id
                    existing.marked_at = datetime.now(UTC)
                    existing.remarks = item.remarks
                    existing.metadata_ = item.metadata
                    records.append(existing)
            if payload.submit_session:
                attendance_session.status = StudentAttendanceSessionStatus.SUBMITTED.value
                attendance_session.submitted_at = datetime.now(UTC)
            await self.session.flush()
            for record in records:
                await self.session.refresh(record)
            response = [self._student_record_read(record) for record in records]
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "student_attendance_conflict",
                "Student attendance could not be saved because of conflicting records.",
                status_code=409,
            ) from exc
        await self._publish_event(
            "attendance.student_records.marked",
            context,
            principal,
            attendance_session.id,
        )
        return response

    async def update_student_record(
        self,
        context: TenantContext,
        principal: Principal,
        record_id: uuid.UUID,
        payload: StudentAttendanceRecordUpdate,
    ) -> StudentAttendanceRecordRead:
        tenant_id = self._require_tenant_id(context)
        record = await self._get_student_record_or_raise(tenant_id, record_id)
        attendance_session = await self._get_student_session_or_raise(tenant_id, record.session_id)
        self._assert_session_writable(attendance_session)
        if payload.status is not None:
            record.status = payload.status.value
        if payload.remarks is not None:
            record.remarks = payload.remarks
        if payload.metadata is not None:
            record.metadata_ = payload.metadata
        record.marked_by = principal.user_id
        record.marked_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(record)
        response = self._student_record_read(record)
        await self.session.commit()
        await self._publish_event(
            "attendance.student_record.updated",
            context,
            principal,
            record.id,
        )
        return response

    async def student_summary(
        self,
        context: TenantContext,
        *,
        start_date: date,
        end_date: date,
        batch_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
    ) -> StudentAttendanceSummaryRead:
        tenant_id = self._require_tenant_id(context)
        self._assert_date_range(start_date, end_date)
        if batch_id is not None:
            await self._validate_batch(tenant_id, batch_id)
        if student_id is not None:
            await self._validate_student(tenant_id, student_id)
        records = await self.student_records.list_for_summary(
            tenant_id,
            start_date=start_date,
            end_date=end_date,
            batch_id=batch_id,
            student_id=student_id,
        )
        grouped: dict[uuid.UUID, list[StudentAttendanceRecord]] = defaultdict(list)
        for record in records:
            grouped[record.student_id].append(record)
        items = [
            self._student_summary_item(current_student_id, current_records)
            for current_student_id, current_records in sorted(grouped.items())
        ]
        return StudentAttendanceSummaryRead(
            start_date=start_date,
            end_date=end_date,
            batch_id=batch_id,
            student_id=student_id,
            items=items,
        )

    async def employee_check_in(
        self,
        context: TenantContext,
        principal: Principal,
        payload: EmployeeCheckInRequest,
    ) -> EmployeeAttendanceRecordRead:
        tenant_id = self._require_tenant_id(context)
        await self._validate_employee(tenant_id, payload.employee_id)
        check_in_at = self._coerce_datetime(payload.check_in_at)
        existing = await self.employee_records.get_for_employee_date(
            tenant_id,
            payload.employee_id,
            check_in_at.date(),
        )
        if existing is not None:
            if payload.idempotency_key and existing.idempotency_key == payload.idempotency_key:
                return self._employee_record_read(existing)
            raise PrepSuiteError(
                "employee_attendance_already_checked_in",
                "Employee attendance already exists for this date.",
                status_code=409,
            )
        record = EmployeeAttendanceRecord(
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            date=check_in_at.date(),
            check_in_at=check_in_at,
            status=EmployeeAttendanceStatus.PRESENT.value,
            source=payload.source.value,
            marked_by=principal.user_id,
            remarks=payload.remarks,
            idempotency_key=payload.idempotency_key,
            metadata_=payload.metadata,
        )
        await self.employee_records.add(record)
        await self.session.refresh(record)
        response = self._employee_record_read(record)
        await self.session.commit()
        await self._publish_event("attendance.employee.checked_in", context, principal, record.id)
        return response

    async def employee_check_out(
        self,
        context: TenantContext,
        principal: Principal,
        payload: EmployeeCheckOutRequest,
    ) -> EmployeeAttendanceRecordRead:
        tenant_id = self._require_tenant_id(context)
        await self._validate_employee(tenant_id, payload.employee_id)
        check_out_at = self._coerce_datetime(payload.check_out_at)
        record = await self.employee_records.get_for_employee_date(
            tenant_id,
            payload.employee_id,
            check_out_at.date(),
        )
        if record is None:
            raise PrepSuiteError(
                "employee_attendance_not_found",
                "Employee attendance check-in was not found for this date.",
                status_code=404,
            )
        if (
            record.check_in_at is not None
            and check_out_at < self._coerce_datetime(record.check_in_at)
        ):
            raise PrepSuiteError(
                "employee_checkout_before_checkin",
                "Check-out time cannot be before check-in time.",
                status_code=422,
            )
        record.check_out_at = check_out_at
        if payload.status is not None:
            record.status = payload.status.value
        record.marked_by = principal.user_id
        if payload.remarks is not None:
            record.remarks = payload.remarks
        await self.session.flush()
        await self.session.refresh(record)
        response = self._employee_record_read(record)
        await self.session.commit()
        await self._publish_event("attendance.employee.checked_out", context, principal, record.id)
        return response

    async def employee_summary(
        self,
        context: TenantContext,
        *,
        start_date: date,
        end_date: date,
        employee_id: uuid.UUID | None,
    ) -> EmployeeAttendanceSummaryRead:
        tenant_id = self._require_tenant_id(context)
        self._assert_date_range(start_date, end_date)
        if employee_id is not None:
            await self._validate_employee(tenant_id, employee_id)
        records = await self.employee_records.list_for_summary(
            tenant_id,
            start_date=start_date,
            end_date=end_date,
            employee_id=employee_id,
        )
        grouped: dict[uuid.UUID, list[EmployeeAttendanceRecord]] = defaultdict(list)
        for record in records:
            grouped[record.employee_id].append(record)
        items = [
            self._employee_summary_item(current_employee_id, current_records)
            for current_employee_id, current_records in sorted(grouped.items())
        ]
        return EmployeeAttendanceSummaryRead(
            start_date=start_date,
            end_date=end_date,
            employee_id=employee_id,
            items=items,
        )

    async def create_correction_request(
        self,
        context: TenantContext,
        principal: Principal,
        payload: AttendanceCorrectionCreate,
    ) -> AttendanceCorrectionRead:
        tenant_id = self._require_tenant_id(context)
        self._validate_requested_status(payload)
        await self._validate_correction_target(tenant_id, payload)
        correction = AttendanceCorrectionRequest(
            tenant_id=tenant_id,
            requester_user_id=principal.user_id,
            target_type=payload.target_type.value,
            student_record_id=payload.student_record_id,
            employee_record_id=payload.employee_record_id,
            requested_status=payload.requested_status,
            reason=payload.reason,
            metadata_=payload.metadata,
        )
        await self.corrections.add(correction)
        await self.session.refresh(correction)
        response = self._correction_read(correction)
        await self.session.commit()
        await self._publish_event(
            "attendance.correction.requested",
            context,
            principal,
            correction.id,
        )
        return response

    async def approve_correction_request(
        self,
        context: TenantContext,
        principal: Principal,
        correction_id: uuid.UUID,
        payload: AttendanceCorrectionApproveRequest,
    ) -> AttendanceCorrectionRead:
        tenant_id = self._require_tenant_id(context)
        correction = await self._get_correction_or_raise(tenant_id, correction_id)
        if correction.status != AttendanceCorrectionStatus.PENDING.value:
            raise PrepSuiteError(
                "attendance_correction_closed",
                "Attendance correction request is already closed.",
                status_code=409,
            )
        correction.status = (
            AttendanceCorrectionStatus.APPROVED.value
            if payload.approved
            else AttendanceCorrectionStatus.REJECTED.value
        )
        correction.reviewed_by = principal.user_id
        correction.reviewed_at = datetime.now(UTC)
        correction.reviewer_note = payload.reviewer_note
        if payload.approved:
            await self._apply_correction(tenant_id, correction)
        await self.session.flush()
        await self.session.refresh(correction)
        response = self._correction_read(correction)
        await self.session.commit()
        await self._publish_event(
            "attendance.correction.reviewed",
            context,
            principal,
            correction.id,
        )
        return response

    async def _validate_correction_target(
        self,
        tenant_id: uuid.UUID,
        payload: AttendanceCorrectionCreate,
    ) -> None:
        if payload.target_type == AttendanceCorrectionTarget.STUDENT_RECORD:
            if payload.student_record_id is None:
                raise PrepSuiteError(
                    "attendance_correction_target_required",
                    "Student correction requires a student record.",
                    status_code=422,
                )
            await self._get_student_record_or_raise(tenant_id, payload.student_record_id)
            return
        if payload.employee_record_id is None:
            raise PrepSuiteError(
                "attendance_correction_target_required",
                "Employee correction requires an employee record.",
                status_code=422,
            )
        await self._get_employee_record_or_raise(tenant_id, payload.employee_record_id)

    async def _apply_correction(
        self,
        tenant_id: uuid.UUID,
        correction: AttendanceCorrectionRequest,
    ) -> None:
        if correction.target_type == AttendanceCorrectionTarget.STUDENT_RECORD.value:
            if correction.student_record_id is None:
                return
            record = await self._get_student_record_or_raise(
                tenant_id,
                correction.student_record_id,
            )
            record.status = correction.requested_status
            record.marked_at = datetime.now(UTC)
            return
        if correction.employee_record_id is None:
            return
        employee_record = await self._get_employee_record_or_raise(
            tenant_id,
            correction.employee_record_id,
        )
        employee_record.status = correction.requested_status

    def _validate_requested_status(self, payload: AttendanceCorrectionCreate) -> None:
        if payload.target_type == AttendanceCorrectionTarget.STUDENT_RECORD:
            allowed = {item.value for item in StudentAttendanceStatus}
        else:
            allowed = {item.value for item in EmployeeAttendanceStatus}
        if payload.requested_status not in allowed:
            raise PrepSuiteError(
                "attendance_correction_invalid_status",
                "Requested status is not valid for the selected attendance record type.",
                status_code=422,
            )

    def _student_summary_item(
        self,
        student_id: uuid.UUID,
        records: list[StudentAttendanceRecord],
    ) -> StudentAttendanceSummaryItem:
        total = len(records)
        present = self._count_student_status(records, StudentAttendanceStatus.PRESENT)
        late = self._count_student_status(records, StudentAttendanceStatus.LATE)
        absent = self._count_student_status(records, StudentAttendanceStatus.ABSENT)
        excused = self._count_student_status(records, StudentAttendanceStatus.EXCUSED)
        attended = present + late + excused
        return StudentAttendanceSummaryItem(
            student_id=student_id,
            total_records=total,
            present_count=present,
            absent_count=absent,
            late_count=late,
            excused_count=excused,
            attendance_percentage=self._percentage(Decimal(attended), Decimal(total)),
        )

    def _employee_summary_item(
        self,
        employee_id: uuid.UUID,
        records: list[EmployeeAttendanceRecord],
    ) -> EmployeeAttendanceSummaryItem:
        total = len(records)
        present = self._count_employee_status(records, EmployeeAttendanceStatus.PRESENT)
        late = self._count_employee_status(records, EmployeeAttendanceStatus.LATE)
        absent = self._count_employee_status(records, EmployeeAttendanceStatus.ABSENT)
        half_day = sum(
            1 for record in records if record.status == EmployeeAttendanceStatus.HALF_DAY.value
        )
        on_leave = sum(
            1 for record in records if record.status == EmployeeAttendanceStatus.ON_LEAVE.value
        )
        attended = Decimal(present + late) + (Decimal(half_day) * Decimal("0.50"))
        work_seconds = sum(self._work_seconds(record) for record in records)
        return EmployeeAttendanceSummaryItem(
            employee_id=employee_id,
            total_days=total,
            present_count=present,
            late_count=late,
            absent_count=absent,
            half_day_count=half_day,
            on_leave_count=on_leave,
            attendance_percentage=self._percentage(attended, Decimal(total)),
            total_work_seconds=work_seconds,
        )

    def _count_student_status(
        self,
        records: list[StudentAttendanceRecord],
        status: StudentAttendanceStatus,
    ) -> int:
        return sum(1 for record in records if record.status == status.value)

    def _count_employee_status(
        self,
        records: list[EmployeeAttendanceRecord],
        status: EmployeeAttendanceStatus,
    ) -> int:
        return sum(1 for record in records if record.status == status.value)

    def _work_seconds(self, record: EmployeeAttendanceRecord) -> int:
        if record.check_in_at is None or record.check_out_at is None:
            return 0
        return max(
            0,
            int(
                (
                    self._coerce_datetime(record.check_out_at)
                    - self._coerce_datetime(record.check_in_at)
                ).total_seconds()
            ),
        )

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

    async def _validate_student(self, tenant_id: uuid.UUID, student_id: uuid.UUID) -> None:
        exists = await self.session.scalar(
            select(Student.id).where(
                Student.tenant_id == tenant_id,
                Student.id == student_id,
                Student.deleted_at.is_(None),
            )
        )
        if exists is None:
            raise PrepSuiteError("student_not_found", "Student was not found.", status_code=404)

    async def _validate_student_membership(
        self,
        tenant_id: uuid.UUID,
        batch_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> None:
        await self._validate_student(tenant_id, student_id)
        membership = await self.session.scalar(
            select(BatchStudent.id).where(
                BatchStudent.tenant_id == tenant_id,
                BatchStudent.batch_id == batch_id,
                BatchStudent.student_id == student_id,
                BatchStudent.status == "active",
            )
        )
        if membership is None:
            raise PrepSuiteError(
                "student_not_in_batch",
                "Student does not belong to the attendance session batch.",
                status_code=403,
            )

    async def _validate_employee(self, tenant_id: uuid.UUID, employee_id: uuid.UUID) -> None:
        exists = await self.session.scalar(
            select(Employee.id).where(
                Employee.tenant_id == tenant_id,
                Employee.id == employee_id,
                Employee.deleted_at.is_(None),
            )
        )
        if exists is None:
            raise PrepSuiteError("employee_not_found", "Employee was not found.", status_code=404)

    async def _get_student_session_or_raise(
        self,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> StudentAttendanceSession:
        attendance_session = await self.student_sessions.get_for_tenant(tenant_id, session_id)
        if attendance_session is None:
            raise PrepSuiteError(
                "student_attendance_session_not_found",
                "Student attendance session was not found.",
                status_code=404,
            )
        return attendance_session

    async def _get_student_record_or_raise(
        self,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> StudentAttendanceRecord:
        record = await self.student_records.get_for_tenant(tenant_id, record_id)
        if record is None:
            raise PrepSuiteError(
                "student_attendance_record_not_found",
                "Student attendance record was not found.",
                status_code=404,
            )
        return record

    async def _get_employee_record_or_raise(
        self,
        tenant_id: uuid.UUID,
        record_id: uuid.UUID,
    ) -> EmployeeAttendanceRecord:
        record = await self.employee_records.get_for_tenant(tenant_id, record_id)
        if record is None:
            raise PrepSuiteError(
                "employee_attendance_record_not_found",
                "Employee attendance record was not found.",
                status_code=404,
            )
        return record

    async def _get_correction_or_raise(
        self,
        tenant_id: uuid.UUID,
        correction_id: uuid.UUID,
    ) -> AttendanceCorrectionRequest:
        correction = await self.corrections.get_for_tenant(tenant_id, correction_id)
        if correction is None:
            raise PrepSuiteError(
                "attendance_correction_not_found",
                "Attendance correction request was not found.",
                status_code=404,
            )
        return correction

    def _assert_session_writable(self, attendance_session: StudentAttendanceSession) -> None:
        if attendance_session.status in LOCKED_SESSION_STATUSES:
            raise PrepSuiteError(
                "student_attendance_session_locked",
                "Student attendance session is not writable.",
                status_code=409,
            )

    def _assert_date_range(self, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise PrepSuiteError(
                "invalid_date_range",
                "end_date must be on or after start_date.",
                status_code=422,
            )

    def _student_session_read(
        self,
        attendance_session: StudentAttendanceSession,
    ) -> StudentAttendanceSessionRead:
        return StudentAttendanceSessionRead.model_validate(attendance_session)

    def _student_record_read(self, record: StudentAttendanceRecord) -> StudentAttendanceRecordRead:
        return StudentAttendanceRecordRead.model_validate(record)

    def _employee_record_read(
        self,
        record: EmployeeAttendanceRecord,
    ) -> EmployeeAttendanceRecordRead:
        return EmployeeAttendanceRecordRead.model_validate(record)

    def _correction_read(self, correction: AttendanceCorrectionRequest) -> AttendanceCorrectionRead:
        return AttendanceCorrectionRead.model_validate(correction)

    def _coerce_datetime(self, value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(UTC)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def _percentage(self, numerator: Decimal, denominator: Decimal) -> Decimal:
        if denominator <= 0:
            return Decimal("0.00")
        return ((numerator / denominator) * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
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
