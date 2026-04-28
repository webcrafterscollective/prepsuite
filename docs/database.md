# Database

Phase 1 configures SQLAlchemy 2.x async ORM and Alembic. Phase 2 adds the tenant foundation and PostgreSQL RLS. Phase 3 adds PrepAccess identity, RBAC, and auth-token tables. Phase 4 adds PrepSettings configuration tables. Phase 5 adds PrepStudents lifecycle tables. Phase 6 adds PrepPeople employee and teacher operations tables. Phase 7 adds PrepLearn curriculum tables. Phase 8 adds PrepQuestion question-bank tables. Phase 9 adds PrepAssess assessment and evaluation tables. Phase 10 adds PrepAttend attendance operation tables. Phase 11 adds PrepLive scheduling and live-service integration tables.

## Connection

The API reads `PREPSUITE_DATABASE_URL`, defaulting to the non-superuser app role:

```text
postgresql+asyncpg://prepsuite_app:prepsuite_app@localhost:5432/prepsuite
```

Alembic reads `PREPSUITE_MIGRATION_DATABASE_URL`, defaulting to the owner role:

```text
postgresql+asyncpg://prepsuite_owner:prepsuite_owner@localhost:5432/prepsuite
```

## Shared Model Base

`app/shared/models.py` defines:

- `Base`: SQLAlchemy declarative base with naming conventions.
- `UUIDPrimaryKeyMixin`: UUID primary key helper.
- `TimestampMixin`: `created_at` and `updated_at` columns.

## Migrations

Run migrations with:

```bash
make migrate
```

The initial revision is a no-op bootstrap migration. The Phase 2 revision creates:

- `tenants`
- `tenant_domains`
- `app_catalog`
- `tenant_apps`
- `tenant_settings`
- `tenant_branding`
- `tenant_users`

The Phase 3 revision creates:

- `users`
- `user_profiles`
- `permissions`
- `roles`
- `role_permissions`
- `user_roles`
- `refresh_tokens`
- `login_sessions`
- `login_history`
- `password_reset_tokens`
- `invitation_tokens`

It also adds `tenant_users.user_id -> users.id`.

The Phase 4 revision creates:

- `tenant_academic_years`
- `tenant_grading_rules`
- `tenant_attendance_rules`
- `tenant_integrations`
- `tenant_app_settings`

The Phase 5 revision creates:

- `students`
- `guardians`
- `student_guardians`
- `batches`
- `batch_students`
- `student_enrollments`
- `student_notes`
- `student_documents`
- `student_status_history`

The Phase 6 revision creates:

- `departments`
- `employees`
- `employee_profiles`
- `employee_documents`
- `teacher_assignments`
- `employee_status_history`
- `employee_notes`

The Phase 7 revision creates:

- `courses`
- `course_modules`
- `lessons`
- `lesson_resources`
- `course_batches`
- `course_teachers`
- `course_publish_history`
- `course_prerequisites`

The Phase 8 revision creates:

- `question_topics`
- `questions`
- `question_options`
- `question_tags`
- `question_sets`
- `question_set_items`
- `ai_question_generation_jobs`

The Phase 9 revision creates:

- `assessments`
- `assessment_sections`
- `assessment_questions`
- `assessment_attempts`
- `assessment_answers`
- `assessment_evaluations`
- `assessment_results`
- `assignment_submissions`
- `evaluation_comments`

The Phase 10 revision creates:

- `student_attendance_sessions`
- `student_attendance_records`
- `employee_attendance_records`
- `attendance_correction_requests`
- `attendance_policies`

The Phase 11 revision creates:

- `live_classes`
- `live_class_participants`
- `live_class_invites`
- `live_class_attendance_snapshots`
- `live_class_recordings`
- `live_class_events`

RLS is enabled and forced on tenant-owned tables. The policy pattern is:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`tenant_domains` allows public SELECT for domain resolution but enforces tenant-scoped writes. `tenant_users` adds a self-resolution SELECT policy based on `app.current_user_id`.

PrepAccess tenant-owned auth tables use the same tenant setting, with self-access policies where token/session lookup needs `app.current_user_id`. Refresh, reset, and invitation tokens are stored only as SHA-256 hashes; their raw values include a tenant/user scope prefix so the application can set RLS context before querying the hash.

PrepSettings tenant-owned tables use the same RLS policy and are accessed only through tenant-scoped sessions. `tenant_app_settings.app_code` references the global `app_catalog`, while subscription state remains owned by `tenant_apps`.

PrepStudents tenant-owned tables also use the same forced RLS policy. The key relationships are:

- `students.tenant_id -> tenants.id` and tenant-unique `admission_no`.
- `guardians.tenant_id -> tenants.id`.
- `student_guardians.student_id -> students.id` and `guardian_id -> guardians.id`.
- `batches.tenant_id -> tenants.id` and tenant-unique `code`.
- `batch_students.batch_id -> batches.id` and `student_id -> students.id`.
- `student_enrollments.student_id -> students.id`, optional `batch_id -> batches.id`, and future-compatible `course_id` UUID.
- `student_notes`, `student_documents`, and `student_status_history` belong to `students`.

`students`, `guardians`, `batches`, and `student_documents` use `deleted_at` soft delete markers. Batch membership removal is represented by `batch_students.status=removed` with `left_at`.

PrepPeople tenant-owned tables use the same forced RLS policy. The key relationships are:

- `departments.tenant_id -> tenants.id` and tenant-unique `code`.
- `employees.tenant_id -> tenants.id`, tenant-unique `employee_code`, optional `user_id -> users.id`, and optional `department_id -> departments.id`.
- `employee_profiles.employee_id -> employees.id`.
- `employee_documents.employee_id -> employees.id`.
- `teacher_assignments.teacher_id -> employees.id`, optional `batch_id -> batches.id`, and future-compatible `course_id` UUID.
- `employee_status_history.employee_id -> employees.id`.
- `employee_notes.employee_id -> employees.id`.

`departments`, `employees`, and `employee_documents` use `deleted_at` soft delete markers. Teacher assignment services validate that only employees with `employee_type=teacher` can receive teaching workload assignments.

PrepLearn tenant-owned tables use the same forced RLS policy. The key relationships are:

- `courses.tenant_id -> tenants.id`, tenant-unique `slug`, optional `created_by -> users.id`, and soft delete.
- `course_modules.course_id -> courses.id`, tenant-scoped unique `(course_id, order_index)`, and soft delete.
- `lessons.module_id -> course_modules.id`, tenant-scoped unique `(module_id, order_index)`, JSON `content`, JSON `completion_rule`, and soft delete.
- `lesson_resources.lesson_id -> lessons.id`, optional future-compatible `content_asset_id`, JSON `metadata`, and soft delete.
- `course_batches.course_id -> courses.id` and `batch_id -> batches.id`, unique per course/batch.
- `course_teachers.course_id -> courses.id` and `teacher_id -> employees.id`, unique per course/teacher.
- `course_publish_history.course_id -> courses.id`, status transition values, `published_by` UUID, and notes.
- `course_prerequisites.course_id -> courses.id` and `prerequisite_course_id -> courses.id`.

PrepLearn services validate cross-module ownership in the application layer before writing assignment rows. Course publishing requires at least one active module and at least one active lesson in every module.

PrepQuestion tenant-owned tables use the same forced RLS policy. The key relationships are:

- `question_topics.tenant_id -> tenants.id`, optional self-parent, and tenant-unique `slug`.
- `questions.topic_id -> question_topics.id`, JSON `metadata`, options/tags relationships, and soft delete.
- `question_options.question_id -> questions.id`, tenant-scoped unique option ordering.
- `question_tags.question_id -> questions.id`, tenant-scoped unique tag names per question.
- `question_sets.tenant_id -> tenants.id`, tenant-unique title, JSON difficulty/topic distributions, total marks, and soft delete.
- `question_set_items.question_set_id -> question_sets.id` and `question_id -> questions.id`, unique question membership, and unique ordering per set.
- `ai_question_generation_jobs.tenant_id -> tenants.id`, requested user UUID, provider-neutral output JSON, and review timestamp.

PrepQuestion services validate option correctness by question type, enforce status transitions, recalculate question-set aggregate marks/distributions, and keep AI integration provider-neutral until a real provider is selected.

PrepAssess tenant-owned tables use the same forced RLS policy. The key relationships are:

- `assessments.tenant_id -> tenants.id`, optional `course_id -> courses.id`, optional `batch_id -> batches.id`, optional `question_set_id -> question_sets.id`, optional `created_by -> users.id`, JSON `settings`, status, schedule window, and soft delete.
- `assessment_sections.assessment_id -> assessments.id`, tenant-scoped unique `(assessment_id, order_index)`, and section-level total marks.
- `assessment_questions.assessment_id -> assessments.id`, optional `section_id -> assessment_sections.id`, `question_id -> questions.id`, tenant-scoped unique `(assessment_id, order_index)`, mark overrides, and JSON `metadata`.
- `assessment_attempts.assessment_id -> assessments.id` and `student_id -> students.id`, unique `(tenant_id, assessment_id, student_id)`, score, status, and JSON `metadata`.
- `assessment_answers.attempt_id -> assessment_attempts.id`, `assessment_question_id -> assessment_questions.id`, `question_id -> questions.id`, JSON `answer`, evaluation status, score, and optional idempotency key.
- `assessment_evaluations.attempt_id -> assessment_attempts.id`, optional evaluator UUID, total score, evaluated timestamp, and JSON `metadata`.
- `assessment_results.assessment_id -> assessments.id`, `student_id -> students.id`, `attempt_id -> assessment_attempts.id`, unique `(tenant_id, assessment_id, student_id)`, percentage, status, and publish timestamp.
- `assignment_submissions.assessment_id -> assessments.id`, `student_id -> students.id`, optional `attempt_id -> assessment_attempts.id`, JSON content, storage key, and status.
- `evaluation_comments.answer_id -> assessment_answers.id`, optional `evaluation_id -> assessment_evaluations.id`, author UUID, visibility, and comment text.

PrepAssess services snapshot question-set membership into `assessment_questions`, validate schedule/publish preconditions, enforce student ownership and optional batch membership before attempts, support idempotent answer submissions, auto-score objective question types, and publish results only after evaluated result rows exist.

PrepAttend tenant-owned tables use the same forced RLS policy. The key relationships are:

- `student_attendance_sessions.tenant_id -> tenants.id`, `batch_id -> batches.id`, optional future-compatible `course_id` and `live_class_id`, attendance date, marker UUID, status, submitted timestamp, and JSON metadata.
- `student_attendance_records.session_id -> student_attendance_sessions.id`, `student_id -> students.id`, tenant-scoped unique `(session_id, student_id)`, attendance status, marker UUID, marked timestamp, remarks, and JSON metadata.
- `employee_attendance_records.employee_id -> employees.id`, tenant-scoped unique `(employee_id, date)`, check-in/out timestamps, status, source, marker UUID, optional idempotency key, remarks, and JSON metadata.
- `attendance_correction_requests` points to either a student record or employee record, tracks requested status, reason, review status, reviewer UUID, reviewed timestamp, reviewer note, and JSON metadata.
- `attendance_policies.tenant_id -> tenants.id`, tenant-unique `code`, scope, minimum percentage, late/absent thresholds, JSON settings, status, default flag, and soft delete.

PrepAttend services validate active student batch membership before marking student records, validate employee ownership before check-in/check-out, replay employee check-in idempotency keys, and apply approved corrections through explicit correction workflow records.

PrepLive tenant-owned tables use the same forced RLS policy. The key relationships are:

- `live_classes.tenant_id -> tenants.id`, optional `course_id -> courses.id`, `batch_id -> batches.id`, `instructor_id -> employees.id`, globally unique `class_code`, timing window, capacity, status, provider, public link, JSON settings, and creator UUID.
- `live_class_participants.live_class_id -> live_classes.id`, optional `user_id`, optional `student_id -> students.id`, optional `employee_id -> employees.id`, participant role, join status, joined/left timestamps, and duration seconds.
- `live_class_invites.live_class_id -> live_classes.id`, tenant/class/email unique guest invitation metadata for future invite flows.
- `live_class_attendance_snapshots.live_class_id -> live_classes.id`, captured timestamp, participant count, and JSON payload from the live runtime.
- `live_class_recordings.live_class_id -> live_classes.id`, provider/storage/playback metadata, duration, status, and JSON metadata.
- `live_class_events.live_class_id -> live_classes.id`, optional `participant_id -> live_class_participants.id`, event type, occurred timestamp, and JSON payload.

PrepLive services validate batch ownership, optional course-batch assignment, instructor assignment, join windows, participant role eligibility, capacity, and cross-tenant access before returning live-service access decisions.
