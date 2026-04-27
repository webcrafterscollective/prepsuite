# Phase 7: PrepLearn

## Goal

Implement curriculum management for tenant institutions. PrepLearn covers courses, modules, lessons, lesson resources, course publishing, course-to-batch mappings, course-to-teacher mappings, prerequisites, and student-facing outline reads.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `courses` | Core course metadata, slug, status, visibility, creator, publish timestamp, and soft delete. | `tenant_id -> tenants.id`; optional `created_by -> users.id`; unique `(tenant_id, slug)`. |
| `course_modules` | Ordered curriculum modules inside a course. | `course_id -> courses.id`; unique `(tenant_id, course_id, order_index)`. |
| `lessons` | Ordered lessons inside a module with JSON content and completion rules. | `module_id -> course_modules.id`; unique `(tenant_id, module_id, order_index)`. |
| `lesson_resources` | Metadata for lesson files, links, embeds, and future content assets. | `lesson_id -> lessons.id`; optional future-compatible `content_asset_id`. |
| `course_batches` | Course assignment to PrepStudents batches. | `course_id -> courses.id`; `batch_id -> batches.id`; unique `(tenant_id, course_id, batch_id)`. |
| `course_teachers` | Course assignment to PrepPeople teacher employees. | `course_id -> courses.id`; `teacher_id -> employees.id`; unique `(tenant_id, course_id, teacher_id)`. |
| `course_publish_history` | Course status transition trail for publishing. | `course_id -> courses.id`; `published_by` UUID. |
| `course_prerequisites` | Course-to-course prerequisite links. | `course_id -> courses.id`; `prerequisite_course_id -> courses.id`. |

All tables include `tenant_id`, timestamps, and forced RLS using:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`courses`, `course_modules`, `lessons`, and `lesson_resources` use soft deletion.

## Classes and Methods

- `CourseRepository.list_for_tenant`: cursor pagination with status, search, and sort support.
- `CourseRepository.detail`: eager-loads modules, lessons, resources, assignments, publish history, and prerequisites.
- `CourseModuleRepository.next_order_index`: computes the next tenant/course-safe module order.
- `LessonRepository.next_order_index`: computes the next tenant/module-safe lesson order.
- `CourseBatchRepository.get_assignment` and `CourseTeacherRepository.get_assignment`: idempotent assignment lookup helpers.
- `PrepLearnService.create_course`: creates a draft course with normalized slug and emits `course.created`.
- `PrepLearnService.publish_course`: validates publish rules, writes publish history, and emits `course.published`.
- `PrepLearnService.reorder_course`: validates ownership and applies two-step order updates to avoid unique-index collisions.
- `PrepLearnService.assign_batch`: validates PrepStudents batch ownership before assignment.
- `PrepLearnService.assign_teacher`: validates PrepPeople employee ownership and `employee_type=teacher`.
- `PrepLearnService.get_detail` and `get_outline`: assemble API read models without lazy-loading at the router layer.

Routes remain thin. Repositories own SQLAlchemy queries only. Services own tenant guards, cross-module validation, publishing rules, events, and transaction boundaries.

## Permissions and Feature Gate

Every endpoint requires `preplearn` to be enabled in `tenant_apps`.

- `preplearn.course.read`
- `preplearn.course.create`
- `preplearn.course.update`
- `preplearn.course.delete`
- `preplearn.course.publish`
- `preplearn.course.assign`

Institution admins receive these permissions through the default role catalog when they are registered.

## API Endpoints

- `GET /api/v1/learn/courses`
- `POST /api/v1/learn/courses`
- `GET /api/v1/learn/courses/{course_id}`
- `PATCH /api/v1/learn/courses/{course_id}`
- `DELETE /api/v1/learn/courses/{course_id}`
- `POST /api/v1/learn/courses/{course_id}/publish`
- `POST /api/v1/learn/courses/{course_id}/archive`
- `POST /api/v1/learn/courses/{course_id}/modules`
- `PATCH /api/v1/learn/modules/{module_id}`
- `POST /api/v1/learn/modules/{module_id}/lessons`
- `PATCH /api/v1/learn/lessons/{lesson_id}`
- `POST /api/v1/learn/courses/{course_id}/reorder`
- `POST /api/v1/learn/courses/{course_id}/assign-batch`
- `POST /api/v1/learn/courses/{course_id}/assign-teacher`
- `GET /api/v1/learn/courses/{course_id}/outline`

`GET /learn/courses` returns `CursorPage[CourseRead]` and supports `limit`, `cursor`, `status`, `search`, and `sort`.

## Events

The in-process event dispatcher emits:

- `course.created`
- `course.updated`
- `course.deleted`
- `course.published`
- `course.archived`
- `course.module.created`
- `course.module.updated`
- `course.lesson.created`
- `course.lesson.updated`
- `course.reordered`
- `course.batch_assigned`
- `course.teacher_assigned`

Phase 23 will route these through the transactional outbox.

## Tests

Phase 7 tests cover:

- Course creation, duplicate slug handling, listing, search, and draft status filtering.
- Publish rules for empty courses and modules without lessons.
- Module and lesson creation with automatic order indexes.
- Reordering modules and lessons.
- Batch assignment and teacher assignment validation.
- Publish, outline, archive, and archived-publish rejection workflows.
- Disabled app response, permission denial, and cross-tenant isolation.

Run:

```bash
uv run pytest tests/learn/test_learn_api.py
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
