# Phase 10: PrepAttend

## Goal

Implement tenant-owned student and employee attendance operations. PrepAttend covers batch-scoped student sessions, bulk student attendance marking, employee check-in/check-out, correction request approval, summary reporting, attendance policy storage, RBAC, app gates, and RLS isolation.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `student_attendance_sessions` | Batch/date attendance session with optional course and future live class reference. | `tenant_id -> tenants.id`; `batch_id -> batches.id`. |
| `student_attendance_records` | One attendance mark per student per session. | `session_id -> student_attendance_sessions.id`; `student_id -> students.id`; unique `(tenant_id, session_id, student_id)`. |
| `employee_attendance_records` | Daily employee check-in/check-out record. | `employee_id -> employees.id`; unique `(tenant_id, employee_id, date)`. |
| `attendance_correction_requests` | Explicit correction workflow for student or employee attendance records. | Optional `student_record_id -> student_attendance_records.id`; optional `employee_record_id -> employee_attendance_records.id`. |
| `attendance_policies` | Tenant attendance policy storage for future rule enforcement. | `tenant_id -> tenants.id`; unique `(tenant_id, code)`. |

All tables include `tenant_id`, timestamps, and forced RLS using:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`attendance_policies` use soft deletion. Attendance records are preserved as operational and audit-relevant records.

## Classes and Methods

- `StudentAttendanceSessionRepository.get_for_tenant`: tenant-scoped session lookup with records loaded.
- `StudentAttendanceRecordRepository.get_for_session_student`: duplicate-safe upsert lookup for student marks.
- `StudentAttendanceRecordRepository.list_for_summary`: returns date-range records joined through sessions.
- `EmployeeAttendanceRecordRepository.get_for_employee_date`: daily check-in idempotency and check-out lookup.
- `EmployeeAttendanceRecordRepository.list_for_summary`: date-range employee summary source.
- `AttendanceCorrectionRequestRepository.get_for_tenant`: correction workflow lookup.
- `PrepAttendService.create_student_session`: validates batch ownership and creates a session.
- `PrepAttendService.mark_student_records`: validates student membership and bulk creates or updates records.
- `PrepAttendService.update_student_record`: updates one writable student record.
- `PrepAttendService.student_summary`: aggregates student present, absent, late, excused, and percentage values.
- `PrepAttendService.employee_check_in`: validates employee ownership and creates or replays a daily check-in.
- `PrepAttendService.employee_check_out`: validates check-out ordering and updates the daily employee record.
- `PrepAttendService.employee_summary`: aggregates employee attendance counts and total work seconds.
- `PrepAttendService.create_correction_request`: validates target type and requested status.
- `PrepAttendService.approve_correction_request`: approves or rejects the request and applies approved status changes.

Routers stay thin. Services own validation, workflow state, idempotency, summary aggregation, and event emission. Repositories own persistence queries only.

## Permissions and Feature Gate

Every endpoint requires `prepattend` to be enabled in `tenant_apps`.

- `prepattend.attendance.read`
- `prepattend.student.manage`
- `prepattend.employee.manage`
- `prepattend.correction.manage`

The legacy broad permission `prepattend.attendance.manage` remains in the catalog for compatibility.

## API Endpoints

- `POST /api/v1/attend/student-sessions`
- `POST /api/v1/attend/student-sessions/{session_id}/records`
- `PATCH /api/v1/attend/student-records/{record_id}`
- `GET /api/v1/attend/students/summary`
- `POST /api/v1/attend/employees/check-in`
- `POST /api/v1/attend/employees/check-out`
- `GET /api/v1/attend/employees/summary`
- `POST /api/v1/attend/correction-requests`
- `POST /api/v1/attend/correction-requests/{correction_id}/approve`

## Validation Rules

- Student sessions require a batch in the current tenant.
- Student marks require active student membership in the session batch.
- Student sessions with `locked` or `cancelled` status are not directly writable.
- One student attendance record is allowed per session/student pair; repeated bulk marks update that record.
- Employee check-in validates the employee in the current tenant.
- One employee attendance record is allowed per employee/date pair.
- Matching employee check-in idempotency keys replay the existing record.
- Employee check-out requires an existing same-day check-in record.
- Check-out time cannot be before check-in time.
- Correction requests must target exactly one student or employee record.
- Correction requested status must be valid for the selected target type.
- Approved corrections apply the requested status to the target record.

## Events

The in-process event dispatcher emits:

- `attendance.student_session.created`
- `attendance.student_records.marked`
- `attendance.student_record.updated`
- `attendance.employee.checked_in`
- `attendance.employee.checked_out`
- `attendance.correction.requested`
- `attendance.correction.reviewed`

Phase 23 will route these through the transactional outbox.

## Tests

Phase 10 tests cover:

- Student attendance session creation.
- Bulk student record marking and summary aggregation.
- Correction request approval and status application.
- Employee check-in idempotency, check-out, summary counts, and work seconds.
- Disabled app response, permission denial, and cross-tenant isolation.

Run:

```bash
uv run pytest tests/attend/test_attend_api.py
make check
```

## Local Review

```bash
uv sync --all-groups
uv run alembic upgrade head
make check
docker compose up --build
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
curl http://localhost:8000/docs
```
