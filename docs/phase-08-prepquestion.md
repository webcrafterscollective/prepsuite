# Phase 8: PrepQuestion

## Goal

Implement the tenant-owned question bank. PrepQuestion covers topic management, question CRUD, options, tags, approval workflow, question-set building, AI generation metadata, and placeholder-generated candidate approval.

## Data Model

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `question_topics` | Topic taxonomy with tenant-unique slug and optional parent. | `tenant_id -> tenants.id`; `parent_id -> question_topics.id`. |
| `questions` | Core question body, type, difficulty, marks, metadata, status, creator, and soft delete. | `topic_id -> question_topics.id`. |
| `question_options` | Ordered answer options and correctness flags. | `question_id -> questions.id`; unique `(tenant_id, question_id, order_index)`. |
| `question_tags` | Normalized per-question tags. | `question_id -> questions.id`; unique `(tenant_id, question_id, name)`. |
| `question_sets` | Question set metadata, total marks, distributions, status, creator, and soft delete. | `tenant_id -> tenants.id`; unique `(tenant_id, title)`. |
| `question_set_items` | Ordered question membership inside a set. | `question_set_id -> question_sets.id`; `question_id -> questions.id`. |
| `ai_question_generation_jobs` | Provider-neutral AI generation metadata and generated output JSON. | `tenant_id -> tenants.id`; `requested_by` UUID. |

All tables include `tenant_id`, timestamps, and forced RLS using:

```sql
tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
```

`questions` and `question_sets` use soft deletion.

## Classes and Methods

- `QuestionTopicRepository.list_for_tenant`: topic lookup with search and archived inclusion support.
- `QuestionRepository.list_for_tenant`: cursor pagination with status, difficulty, type, topic, tag, search, and sort filters.
- `QuestionSetRepository.detail`: eager-loads set items with questions, options, and tags.
- `QuestionSetItemRepository.next_order_index`: computes the next safe order index for set-builder flows.
- `PrepQuestionService.create_question`: validates topic ownership, marks, options, tags, and creates the question aggregate.
- `PrepQuestionService.update_question`: handles content updates, option/tag replacement, and status transitions.
- `PrepQuestionService.add_question_set_item`: prevents duplicates and recalculates total marks plus difficulty/topic distributions.
- `PrepQuestionService.reorder_question_set`: validates ownership and applies two-step order updates to avoid unique-index collisions.
- `PrepQuestionService.create_ai_generation_job`: creates a completed placeholder generation job through a provider interface.
- `PrepQuestionService.approve_ai_generation_job`: saves selected generated candidates into the question bank and marks the job approved.

Routers stay thin. Services own business rules and events. Repositories own persistence queries only.

## Permissions and Feature Gate

Every endpoint requires `prepquestion` to be enabled in `tenant_apps`.

- `prepquestion.question.read`
- `prepquestion.question.manage`
- `prepquestion.question_set.manage`
- `prepquestion.ai_generation.manage`

Institution admins receive these permissions through the default role catalog when they are registered.

## API Endpoints

- `GET /api/v1/questions/topics`
- `POST /api/v1/questions/topics`
- `GET /api/v1/questions`
- `POST /api/v1/questions`
- `GET /api/v1/questions/{question_id}`
- `PATCH /api/v1/questions/{question_id}`
- `POST /api/v1/question-sets`
- `GET /api/v1/question-sets`
- `GET /api/v1/question-sets/{question_set_id}`
- `POST /api/v1/question-sets/{question_set_id}/items`
- `PATCH /api/v1/question-sets/{question_set_id}/reorder`
- `DELETE /api/v1/question-sets/{question_set_id}/items/{item_id}`
- `POST /api/v1/questions/ai-generation-jobs`
- `GET /api/v1/questions/ai-generation-jobs/{job_id}`
- `POST /api/v1/questions/ai-generation-jobs/{job_id}/approve`

`GET /questions` returns `CursorPage[QuestionRead]` and supports `limit`, `cursor`, `status`, `difficulty`, `question_type`, `topic_id`, `tag`, `search`, and `sort`.

## Validation Rules

- MCQ questions require at least two options and exactly one correct option.
- Multi-select questions require at least two options and at least one correct option.
- True/false questions require exactly two options and one correct option.
- Short answer, long answer, coding, and fill-blank questions do not accept options.
- Negative marks cannot exceed marks.
- Question status transitions follow draft -> reviewed -> approved, with archival allowed from active states.

## Events

The in-process event dispatcher emits:

- `question.topic.created`
- `question.created`
- `question.updated`
- `question_set.created`
- `question_set.item_added`
- `question_set.item_removed`
- `question_set.reordered`
- `question.ai_generation.completed`
- `question.ai_generation.approved`

Phase 23 will route these through the transactional outbox.

## Tests

Phase 8 tests cover:

- Topic creation and duplicate topic conflict.
- MCQ option validation.
- Question create/list/update/status approval flow.
- Metadata and tag normalization.
- Question-set item add, duplicate prevention, total marks, distributions, and reorder.
- AI placeholder job creation and selected candidate approval.
- Disabled app response, permission denial, and cross-tenant isolation.

Run:

```bash
uv run pytest tests/question/test_question_api.py
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
