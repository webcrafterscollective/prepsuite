# Phase 6: PrepPeople

## Goal

Implement employee, staff, and teacher operations for tenant institutions. PrepPeople covers departments, employee directory/profile data, staff document metadata, employee notes/status history, teacher assignments, workload summaries, and optional linking to PrepAccess users.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `departments` | Tenant department records with code, description, status, and soft delete. | `tenant_id -> tenants.id`; unique `(tenant_id, code)`. |
| `employees` | Core employee identity, contact, type, status, optional department, optional PrepAccess user, and soft delete. | `tenant_id -> tenants.id`; `user_id -> users.id`; `department_id -> departments.id`; unique `(tenant_id, employee_code)` and `(tenant_id, user_id)`. |
| `employee_profiles` | Job title, bio, qualifications, emergency contact, and profile JSON. | `employee_id -> employees.id`. |
| `employee_documents` | Document metadata for externally stored HR/staff files. | `employee_id -> employees.id`; `uploaded_by` UUID. |
| `teacher_assignments` | Teacher mapping to course UUID, batch, or both. | `teacher_id -> employees.id`; optional `batch_id -> batches.id`; future-compatible `course_id` UUID. |
| `employee_status_history` | Status transition trail. | `employee_id -> employees.id`; `changed_by` UUID. |
| `employee_notes` | Internal, manager, or HR notes. | `employee_id -> employees.id`; `author_user_id` UUID. |

All tables include `tenant_id`, timestamps, and forced RLS using:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`departments`, `employees`, and `employee_documents` use soft deletion.

## Classes and Methods

- `EmployeeRepository.list_for_tenant`: cursor pagination with status, employee type, department, search, and sort support.
- `EmployeeRepository.profile`: eager-loads employee profile aggregates.
- `DepartmentRepository`: tenant-scoped department lookup and listing.
- `TeacherAssignmentRepository.list_for_teacher`: workload source query.
- `PrepPeopleService.create_employee`: validates optional user/department links, creates profile data, and writes initial status history.
- `PrepPeopleService.update_employee`: updates employee fields and profile, and records status transitions.
- `PrepPeopleService.create_teacher_assignment`: validates teacher type and optional batch ownership.
- `PrepPeopleService.teacher_workload`: summarizes active assignment, course, and batch counts.
- `PrepPeopleService.get_profile` and `timeline`: aggregate views for employee profile screens.

Routers remain thin. Repositories own queries only. Services own tenant guards, cross-module validation, business rules, and event emission.

## Permissions and Feature Gate

Every endpoint requires `preppeople` to be enabled in `tenant_apps`.

- `preppeople.employee.read`
- `preppeople.employee.create`
- `preppeople.employee.update`
- `preppeople.department.manage`
- `preppeople.teacher_assignment.manage`

Institution admins receive these permissions through the default role catalog when they are registered.

## API Endpoints

- `GET /api/v1/people/employees`
- `POST /api/v1/people/employees`
- `GET /api/v1/people/employees/{employee_id}`
- `PATCH /api/v1/people/employees/{employee_id}`
- `GET /api/v1/people/employees/{employee_id}/profile`
- `GET /api/v1/people/employees/{employee_id}/timeline`
- `POST /api/v1/people/employees/{employee_id}/notes`
- `POST /api/v1/people/employees/{employee_id}/documents`
- `GET /api/v1/people/departments`
- `POST /api/v1/people/departments`
- `POST /api/v1/people/teacher-assignments`
- `GET /api/v1/people/teachers/{teacher_id}/workload`

`GET /people/employees` returns `CursorPage[EmployeeRead]` and supports `limit`, `cursor`, `status`, `employee_type`, `department_id`, `search`, and `sort`.

## Events

The in-process event dispatcher emits:

- `employee.created`
- `employee.updated`
- `employee.note_added`
- `employee.document_added`
- `department.created`
- `teacher.assignment.created`

Phase 23 will route these through the transactional outbox.

## Tests

Phase 6 tests cover:

- Department creation.
- Employee creation with linked PrepAccess user and profile.
- Directory filtering and duplicate employee-code conflict handling.
- Employee status/profile updates.
- Employee notes, document metadata, profile aggregate, and timeline.
- Teacher assignment and workload summary.
- Rejection when assigning a non-teacher as teacher.
- Disabled app response, permission denial, and cross-tenant isolation.

Run:

```bash
uv run pytest tests/people/test_people_api.py
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
