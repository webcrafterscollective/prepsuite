# Phase 9: PrepAssess

## Goal

Implement the tenant-owned assessment lifecycle. PrepAssess covers assessments created from question sets, scheduling, publishing, student attempts, idempotent answer submission, objective auto-evaluation, manual evaluation, result publishing, and assessment analytics.

The tenant app code is `prepassess` to match the existing app catalog and permission seed data.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `assessments` | Assessment metadata, type, status, optional schedule, settings, total marks, creator, and soft delete. | `tenant_id -> tenants.id`; optional `course_id -> courses.id`; optional `batch_id -> batches.id`; optional `question_set_id -> question_sets.id`. |
| `assessment_sections` | Ordered sections inside an assessment. | `assessment_id -> assessments.id`; unique `(tenant_id, assessment_id, order_index)`. |
| `assessment_questions` | Snapshot of questions selected for the assessment. | `assessment_id -> assessments.id`; optional `section_id -> assessment_sections.id`; `question_id -> questions.id`. |
| `assessment_attempts` | One student's attempt for one assessment. | `assessment_id -> assessments.id`; `student_id -> students.id`; unique `(tenant_id, assessment_id, student_id)`. |
| `assessment_answers` | Submitted answer JSON plus evaluation state and score. | `attempt_id -> assessment_attempts.id`; `assessment_question_id -> assessment_questions.id`; `question_id -> questions.id`. |
| `assessment_evaluations` | Attempt-level evaluation summary. | `attempt_id -> assessment_attempts.id`; optional evaluator UUID. |
| `assessment_results` | Publishable student result row. | `assessment_id -> assessments.id`; `student_id -> students.id`; `attempt_id -> assessment_attempts.id`. |
| `assignment_submissions` | Assignment submission metadata for assignment-type assessments. | `assessment_id -> assessments.id`; `student_id -> students.id`; optional `attempt_id -> assessment_attempts.id`. |
| `evaluation_comments` | Evaluator comments tied to answers or evaluations. | Optional `answer_id -> assessment_answers.id`; optional `evaluation_id -> assessment_evaluations.id`. |

Every table includes `tenant_id`, timestamps, and forced RLS using:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`assessments` use soft deletion. Attempts and answers are preserved as audit-relevant academic records.

## Classes and Methods

- `AssessmentRepository.list_for_tenant`: cursor pagination with status, type, course, batch, search, and sort filters.
- `AssessmentRepository.detail`: eager-loads sections, questions, attempts, and results for aggregate reads.
- `AssessmentQuestionRepository.list_for_assessment`: returns ordered assessment questions.
- `AssessmentAttemptRepository.get_for_student`: supports idempotent attempt start.
- `AssessmentAnswerRepository.get_for_attempt_question`: supports idempotent answer submission and duplicate prevention.
- `AssessmentAnswerRepository.pending_for_assessment`: powers the manual evaluation queue.
- `AssessmentResultRepository.list_for_assessment`: returns evaluated results for publication and analytics.
- `PrepAssessService.create_assessment`: validates optional course/batch ownership and snapshots a PrepQuestion question set into sections/questions.
- `PrepAssessService.schedule_assessment`: requires at least one question before setting the assessment window.
- `PrepAssessService.publish_assessment`: moves scheduled assessments into live availability.
- `PrepAssessService.start_attempt`: validates timing, student ownership, optional batch membership, and idempotent repeat starts.
- `PrepAssessService.submit_answer`: writes one answer, replays matching idempotency keys, and auto-evaluates MCQ, multi-select, and true/false answers.
- `PrepAssessService.submit_attempt`: submits or auto-submits an attempt and finalizes when all answers are evaluated.
- `PrepAssessService.evaluate_answer`: manually scores subjective answers and finalizes the attempt when complete.
- `PrepAssessService.publish_results`: publishes evaluated result rows and marks the assessment published.
- `PrepAssessService.analytics`: calculates attempt counts, evaluated counts, result counts, and score aggregates.

Routers stay thin. Services own business rules, cross-module validation, scoring, events, and transaction boundaries. Repositories own SQLAlchemy queries only.

## Permissions and Feature Gate

Every endpoint requires `prepassess` to be enabled in `tenant_apps`.

- `prepassess.assessment.read`
- `prepassess.assessment.create`
- `prepassess.assessment.update`
- `prepassess.assessment.schedule`
- `prepassess.assessment.publish`
- `prepassess.attempt.manage`
- `prepassess.evaluation.manage`
- `prepassess.result.publish`

Institution admins receive these permissions through the default role catalog when they are registered.

## API Endpoints

- `GET /api/v1/assessments`
- `POST /api/v1/assessments`
- `GET /api/v1/assessments/{assessment_id}`
- `PATCH /api/v1/assessments/{assessment_id}`
- `POST /api/v1/assessments/{assessment_id}/schedule`
- `POST /api/v1/assessments/{assessment_id}/publish`
- `POST /api/v1/assessments/{assessment_id}/attempts/start`
- `POST /api/v1/assessment-attempts/{attempt_id}/answers`
- `POST /api/v1/assessment-attempts/{attempt_id}/submit`
- `GET /api/v1/assessments/{assessment_id}/evaluation-queue`
- `POST /api/v1/assessment-answers/{answer_id}/evaluate`
- `POST /api/v1/assessments/{assessment_id}/results/publish`
- `GET /api/v1/assessments/{assessment_id}/analytics`

`GET /assessments` returns `CursorPage[AssessmentRead]` and supports `limit`, `cursor`, `status`, `assessment_type`, `course_id`, `batch_id`, `search`, and `sort`.

## Validation Rules

- Assessments created from question sets require the question set to exist and contain at least one item.
- Scheduling requires at least one assessment question.
- Publish requires an assessment window unless `force=true`.
- Attempts are allowed only for scheduled or live assessments within the configured time window.
- Students must belong to the current tenant and, when `batch_id` is set, be active members of the assessment batch.
- A student can have only one attempt per assessment.
- One answer is allowed per assessment question per attempt; matching idempotency keys replay the original answer.
- MCQ, multi-select, and true/false answers are auto-scored from correct option IDs.
- Manual scores cannot exceed the assessment question marks.
- Results can be published only after evaluated result rows exist.

## Events

The in-process event dispatcher emits:

- `assessment.created`
- `assessment.updated`
- `assessment.scheduled`
- `assessment.published`
- `assessment.attempt.started`
- `assessment.answer.submitted`
- `assessment.attempt.submitted`
- `assessment.answer.evaluated`
- `assessment.results.published`

Phase 23 will route these through the transactional outbox.

## Tests

Phase 9 tests cover:

- Assessment creation from a question set.
- Assessment search/list filtering.
- Schedule and publish workflow.
- Idempotent attempt start.
- Idempotent answer submission.
- MCQ auto-evaluation.
- Manual evaluation queue and subjective answer scoring.
- Result publishing and analytics.
- Disabled app response, permission denial, and cross-tenant isolation.

Run:

```bash
uv run pytest tests/assess/test_assess_api.py
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
