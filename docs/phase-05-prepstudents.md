# Phase 5: PrepStudents

## Goal

Implement the first learner-domain bounded context: student lifecycle, guardians, batches, enrollments, notes, document metadata, status history, timeline, and profile aggregation. PrepStudents is tenant-scoped with PostgreSQL RLS, guarded by the `prepstudents` app subscription, and protected by module-specific RBAC permissions.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `students` | Core student identity, contact, demographic, status, join, and soft-delete fields. | `tenant_id -> tenants.id`; unique `(tenant_id, admission_no)`. |
| `guardians` | Guardian identity, contact, relationship metadata, and soft-delete fields. | `tenant_id -> tenants.id`. |
| `student_guardians` | Many-to-many student/guardian links with primary, pickup, and emergency-contact flags. | `student_id -> students.id`; `guardian_id -> guardians.id`. |
| `batches` | Tenant batch/cohort records with optional future `course_id`, date range, capacity, status, and soft delete. | `tenant_id -> tenants.id`; unique `(tenant_id, code)`. |
| `batch_students` | Student membership in batches with active/removed/transferred status. | `batch_id -> batches.id`; `student_id -> students.id`. |
| `student_enrollments` | Course enrollment mapping prepared for PrepLearn. | `student_id -> students.id`; optional `batch_id -> batches.id`; `course_id` UUID placeholder. |
| `student_notes` | Staff notes with visibility classification. | `student_id -> students.id`; `author_user_id` UUID. |
| `student_documents` | Document metadata for externally stored files. | `student_id -> students.id`; `uploaded_by` UUID. |
| `student_status_history` | Status transition audit trail. | `student_id -> students.id`; `changed_by` UUID. |

All tables include `tenant_id`, timestamps, and forced RLS using:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

Business-owned records use soft deletion where appropriate: `students`, `guardians`, `batches`, and `student_documents`.

## Classes and Methods

- `StudentRepository.list_for_tenant`: cursor pagination by `created_at/id`, with status, search, batch, and sort support.
- `StudentRepository.profile`: eager-loads the profile aggregate.
- `BatchStudentRepository.active_count`: enforces batch capacity before assignment.
- `PrepStudentsService.create_student`: creates a student and initial status history.
- `PrepStudentsService.bulk_import_students`: imports up to 500 students, reporting duplicate rows without aborting successful rows.
- `PrepStudentsService.update_student`: updates student fields and records status transitions.
- `PrepStudentsService.delete_student`: soft deletes a student.
- `PrepStudentsService.add_guardian`, `add_note`, `add_document`, `enroll_student`: focused student sub-workflows.
- `PrepStudentsService.create_batch`, `update_batch`, `assign_student_to_batch`, `remove_student_from_batch`: batch lifecycle and capacity-safe membership.
- `PrepStudentsService.get_profile` and `timeline`: read aggregates for frontend profile screens.

Routers stay thin and call service/use-case methods only. Repositories contain SQLAlchemy query logic only.

## Permissions and Feature Gate

Every endpoint requires `prepstudents` to be enabled in `tenant_apps`.

- `prepstudents.student.read`
- `prepstudents.student.create`
- `prepstudents.student.update`
- `prepstudents.student.delete`
- `prepstudents.student.import`
- `prepstudents.batch.manage`

Institution admins receive these permissions through the default role catalog when they are registered.

## API Endpoints

- `GET /api/v1/students`
- `POST /api/v1/students`
- `GET /api/v1/students/{student_id}`
- `PATCH /api/v1/students/{student_id}`
- `DELETE /api/v1/students/{student_id}`
- `POST /api/v1/students/bulk-import`
- `GET /api/v1/students/{student_id}/timeline`
- `GET /api/v1/students/{student_id}/profile`
- `POST /api/v1/students/{student_id}/guardians`
- `POST /api/v1/students/{student_id}/notes`
- `POST /api/v1/students/{student_id}/documents`
- `POST /api/v1/students/{student_id}/enrollments`
- `GET /api/v1/batches`
- `POST /api/v1/batches`
- `GET /api/v1/batches/{batch_id}`
- `PATCH /api/v1/batches/{batch_id}`
- `POST /api/v1/batches/{batch_id}/students`
- `DELETE /api/v1/batches/{batch_id}/students/{student_id}`

`GET /students` returns `CursorPage[StudentRead]` and supports `limit`, `cursor`, `status`, `search`, `batch_id`, and `sort`.

## Events

The in-process event dispatcher emits:

- `student.created`
- `student.updated`
- `student.deleted`
- `student.guardian_added`
- `student.note_added`
- `student.document_added`
- `student.enrolled`
- `student.assigned_to_batch`
- `student.removed_from_batch`
- `batch.created`
- `batch.updated`

Phase 23 will route these through the transactional outbox.

## Tests

Phase 5 tests cover:

- Student lifecycle, duplicate admission number, search/filter, status history, profile, timeline, and soft delete.
- Guardian, note, document metadata, and enrollment creation.
- Bulk import partial success and duplicate payload reporting.
- Batch capacity, assignment, filtered listing, removal, and reassignment.
- Disabled app response.
- Permission denial for users without a PrepStudents role.
- Cross-tenant isolation.

Run:

```bash
uv run pytest tests/students/test_students_api.py
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
