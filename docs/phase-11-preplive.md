# Phase 11: PrepLive Main Backend

## Goal

Implement the main PrepSuite scheduling and access-control backend for PrepLive. The actual classroom runtime remains a separate service; this phase owns tenant-scoped class scheduling, batch and teacher validation, hard-to-guess public links, access validation for the future live service, attendance event capture, recording metadata, RBAC, app gates, and RLS isolation.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `live_classes` | Scheduled class owned by a tenant, batch, instructor, timing window, capacity, provider, and public class code. | `tenant_id -> tenants.id`; `batch_id -> batches.id`; optional `course_id -> courses.id`; `instructor_id -> employees.id`. |
| `live_class_participants` | Allowed or joined participant identity for a class. | `live_class_id -> live_classes.id`; optional user, student, or employee identity. |
| `live_class_invites` | Future guest/invite token records for class access. | `live_class_id -> live_classes.id`; tenant/class/email unique. |
| `live_class_attendance_snapshots` | Snapshot payloads received from the live runtime. | `live_class_id -> live_classes.id`. |
| `live_class_recordings` | Recording metadata supplied by the live runtime or storage pipeline. | `live_class_id -> live_classes.id`. |
| `live_class_events` | Immutable class and participant lifecycle events. | `live_class_id -> live_classes.id`; optional `participant_id`. |

All tables include `tenant_id`, timestamps, and forced RLS using:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

Class codes are globally unique, human-readable, and include a random suffix. Links are generated as `https://live.prepsuite.in/{class_code}`.

## Classes and Methods

- `LiveClassRepository.get_for_tenant`: tenant-scoped class lookup.
- `LiveClassRepository.get_by_code`: class-code lookup for live-link validation.
- `LiveClassRepository.detail`: eager-loaded detail with participants, recordings, and events.
- `LiveClassRepository.list_for_tenant`: cursor list with status, batch, student, teacher, and date filters.
- `LiveClassParticipantRepository.find_identity`: participant lookup by user, student, or employee identity.
- `LiveClassParticipantRepository.active_count`: current capacity source.
- `PrepLiveService.schedule_class`: validates batch, optional course/batch mapping, instructor assignment, creates class, instructor participant, link, and scheduled event.
- `PrepLiveService.update_class`: updates scheduled/open classes with validation and admin override checks.
- `PrepLiveService.cancel_class`: closes a class and emits cancellation events.
- `PrepLiveService.open_class`: moves a scheduled class to open and emits the start event contract.
- `PrepLiveService.end_class`: marks the class ended, completes active participants, and emits end events.
- `PrepLiveService.validate_access`: validates tenant, class status, join window, capacity, student batch membership, employee assignment/admin rules, and records allowed joins.
- `PrepLiveService.capture_attendance_events`: ingests joined/left events and optional snapshots from the live runtime.
- `PrepLiveService.add_recording`: stores recording metadata and emits a recording event.

Routers stay thin. Services own scheduling rules, access validation, state transitions, and event emission. Repositories own SQLAlchemy queries only.

## Permissions and Feature Gate

Every endpoint requires `preplive` to be enabled in `tenant_apps`.

- `preplive.class.schedule`
- `preplive.class.read`
- `preplive.class.manage`
- `preplive.access.validate`
- `preplive.attendance.sync`
- `preplive.recording.manage`

`admin_override=true` is accepted only for principals with `preplive.class.manage`.

## API Endpoints

- `POST /api/v1/live/classes`
- `GET /api/v1/live/classes`
- `GET /api/v1/live/classes/{live_class_id}`
- `PATCH /api/v1/live/classes/{live_class_id}`
- `POST /api/v1/live/classes/{live_class_id}/cancel`
- `POST /api/v1/live/classes/{live_class_id}/open`
- `POST /api/v1/live/classes/{live_class_id}/end`
- `GET /api/v1/live/classes/by-code/{class_code}`
- `POST /api/v1/live/classes/{class_code}/validate-access`
- `POST /api/v1/live/classes/{live_class_id}/attendance-events`
- `POST /api/v1/live/classes/{live_class_id}/recordings`

## Validation Rules

- Batch must belong to the current tenant.
- Optional course must exist in the current tenant and be assigned to the selected batch.
- Instructor must be an active teacher employee.
- Teacher must be assigned to the selected course or batch unless an authorized admin override is used.
- Capacity must be positive.
- Class end time must be after start time.
- Scheduled/open classes can be updated; cancelled/ended classes are locked.
- Join is allowed only within `starts_at - join_before_minutes` and `ends_at + join_after_minutes`.
- Students must belong to the class batch.
- Employees must be the instructor, an assigned teacher, or an admin/manager employee.
- Admin joins require the live class management permission.
- Capacity is enforced before a new participant is admitted.
- Access denials return `allowed=false` with a reason for live-service handling.

## Events

The in-process event dispatcher emits:

- `live.class.scheduled`
- `live.class.cancelled`
- `live.class.started`
- `live.class.ended`
- `live.participant.joined`
- `live.participant.left`
- `live.recording.added`

Phase 23 will route these through the transactional outbox.

## Tests

Phase 11 tests cover:

- Live class scheduling and link generation.
- Class list/detail/by-code reads.
- Open and end transitions.
- Access validation for batch students.
- Capacity enforcement.
- Non-member denial and expired join-window denial.
- Unassigned teacher scheduling rejection.
- Attendance event capture and recording metadata.
- Disabled app rejection, permission denial, and cross-tenant class isolation.

Run:

```bash
uv run pytest tests/live/test_live_api.py
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
