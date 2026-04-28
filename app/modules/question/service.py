from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import TenantContext
from app.modules.question.enums import (
    AIGenerationJobStatus,
    QuestionDifficulty,
    QuestionSetStatus,
    QuestionStatus,
    QuestionType,
    TopicStatus,
)
from app.modules.question.models import (
    AIQuestionGenerationJob,
    Question,
    QuestionOption,
    QuestionSet,
    QuestionSetItem,
    QuestionTag,
    QuestionTopic,
)
from app.modules.question.repository import (
    AIQuestionGenerationJobRepository,
    QuestionOptionRepository,
    QuestionRepository,
    QuestionSetItemRepository,
    QuestionSetRepository,
    QuestionTagRepository,
    QuestionTopicRepository,
)
from app.modules.question.schemas import (
    AIQuestionGenerationApprovalRead,
    AIQuestionGenerationApproveRequest,
    AIQuestionGenerationJobCreate,
    AIQuestionGenerationJobRead,
    QuestionCreate,
    QuestionOptionCreate,
    QuestionOptionRead,
    QuestionPage,
    QuestionRead,
    QuestionSetCreate,
    QuestionSetDetailRead,
    QuestionSetItemCreate,
    QuestionSetItemRead,
    QuestionSetPage,
    QuestionSetRead,
    QuestionSetReorderRequest,
    QuestionTopicCreate,
    QuestionTopicRead,
    QuestionUpdate,
    normalize_tags,
    slugify,
)

OPTION_REQUIRED_TYPES = {
    QuestionType.MCQ,
    QuestionType.MULTI_SELECT,
    QuestionType.TRUE_FALSE,
}
OPTIONLESS_TYPES = {
    QuestionType.SHORT_ANSWER,
    QuestionType.LONG_ANSWER,
    QuestionType.CODING,
    QuestionType.FILL_BLANK,
}
ALLOWED_STATUS_TRANSITIONS: dict[QuestionStatus, set[QuestionStatus]] = {
    QuestionStatus.DRAFT: {QuestionStatus.DRAFT, QuestionStatus.REVIEWED, QuestionStatus.ARCHIVED},
    QuestionStatus.REVIEWED: {
        QuestionStatus.DRAFT,
        QuestionStatus.REVIEWED,
        QuestionStatus.APPROVED,
        QuestionStatus.ARCHIVED,
    },
    QuestionStatus.APPROVED: {
        QuestionStatus.REVIEWED,
        QuestionStatus.APPROVED,
        QuestionStatus.ARCHIVED,
    },
    QuestionStatus.ARCHIVED: {QuestionStatus.ARCHIVED},
}


class QuestionGenerationProvider(Protocol):
    def generate(self, payload: AIQuestionGenerationJobCreate) -> dict[str, Any]:
        """Return provider-neutral candidate question payloads."""


class PlaceholderQuestionGenerationProvider:
    def generate(self, payload: AIQuestionGenerationJobCreate) -> dict[str, Any]:
        questions: list[dict[str, Any]] = []
        for index in range(1, payload.count + 1):
            questions.append(
                {
                    "body": f"{payload.prompt.strip()} ({payload.topic.strip()} #{index})",
                    "explanation": "Placeholder generation output awaiting human review.",
                    "marks": "1.00",
                    "negative_marks": "0.00",
                    "options": self._options_for(payload.question_type),
                    "metadata": {"provider": "placeholder", "candidate_index": index},
                    "tags": ["ai-generated", slugify(payload.topic)],
                }
            )
        return {"provider": "placeholder", "questions": questions}

    def _options_for(self, question_type: QuestionType) -> list[dict[str, Any]]:
        if question_type == QuestionType.MCQ:
            return [
                {"label": "A", "body": "Generated correct answer", "is_correct": True},
                {"label": "B", "body": "Generated distractor", "is_correct": False},
            ]
        if question_type == QuestionType.MULTI_SELECT:
            return [
                {"label": "A", "body": "Generated correct answer", "is_correct": True},
                {"label": "B", "body": "Generated second correct answer", "is_correct": True},
                {"label": "C", "body": "Generated distractor", "is_correct": False},
            ]
        if question_type == QuestionType.TRUE_FALSE:
            return [
                {"label": "T", "body": "True", "is_correct": True},
                {"label": "F", "body": "False", "is_correct": False},
            ]
        return []


class PrepQuestionService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
        generation_provider: QuestionGenerationProvider | None = None,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.generation_provider = generation_provider or PlaceholderQuestionGenerationProvider()
        self.topics = QuestionTopicRepository(session)
        self.questions = QuestionRepository(session)
        self.options = QuestionOptionRepository(session)
        self.tags = QuestionTagRepository(session)
        self.question_sets = QuestionSetRepository(session)
        self.question_set_items = QuestionSetItemRepository(session)
        self.ai_jobs = AIQuestionGenerationJobRepository(session)

    async def list_topics(
        self,
        context: TenantContext,
        *,
        search: str | None,
        include_archived: bool,
    ) -> list[QuestionTopicRead]:
        tenant_id = self._require_tenant_id(context)
        topics = await self.topics.list_for_tenant(
            tenant_id,
            search=search,
            include_archived=include_archived,
        )
        return [QuestionTopicRead.model_validate(topic) for topic in topics]

    async def create_topic(
        self,
        context: TenantContext,
        principal: Principal,
        payload: QuestionTopicCreate,
    ) -> QuestionTopicRead:
        tenant_id = self._require_tenant_id(context)
        if payload.parent_id is not None:
            await self._get_topic_or_raise(tenant_id, payload.parent_id)
        topic = QuestionTopic(
            tenant_id=tenant_id,
            parent_id=payload.parent_id,
            name=payload.name,
            slug=payload.slug or slugify(payload.name),
            description=payload.description,
        )
        try:
            await self.topics.add(topic)
            await self.session.refresh(topic)
            response = QuestionTopicRead.model_validate(topic)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "question_topic_conflict",
                "Question topic slug already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("question.topic.created", context, principal, topic.id)
        return response

    async def list_questions(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor: str | None,
        status: QuestionStatus | None,
        difficulty: QuestionDifficulty | None,
        question_type: QuestionType | None,
        topic_id: uuid.UUID | None,
        tag: str | None,
        search: str | None,
        sort: str,
    ) -> QuestionPage:
        tenant_id = self._require_tenant_id(context)
        result = await self.questions.list_for_tenant(
            tenant_id,
            limit=limit,
            cursor=cursor,
            status=status.value if status else None,
            difficulty=difficulty.value if difficulty else None,
            question_type=question_type.value if question_type else None,
            topic_id=topic_id,
            tag=tag,
            search=search,
            sort=sort,
        )
        return QuestionPage(
            items=[self._question_read(question) for question in result.items],
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    async def create_question(
        self,
        context: TenantContext,
        principal: Principal,
        payload: QuestionCreate,
    ) -> QuestionRead:
        tenant_id = self._require_tenant_id(context)
        await self._get_topic_or_raise(tenant_id, payload.topic_id)
        self._validate_question_payload(
            payload.question_type,
            payload.marks,
            payload.negative_marks,
            payload.options,
        )
        question = Question(
            tenant_id=tenant_id,
            topic_id=payload.topic_id,
            question_type=payload.question_type.value,
            difficulty=payload.difficulty.value,
            bloom_level=payload.bloom_level,
            body=payload.body,
            explanation=payload.explanation,
            marks=payload.marks,
            negative_marks=payload.negative_marks,
            metadata_=payload.metadata,
            status=payload.status.value,
            created_by=principal.user_id,
        )
        try:
            await self.questions.add(question)
            await self._replace_options(tenant_id, question.id, payload.options)
            await self._replace_tags(tenant_id, question.id, payload.tags)
            await self.session.flush()
            response = await self._question_response(tenant_id, question.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "question_conflict",
                "Question could not be created due to a conflicting value.",
                status_code=409,
            ) from exc
        await self._publish_event("question.created", context, principal, question.id)
        return response

    async def get_question(self, context: TenantContext, question_id: uuid.UUID) -> QuestionRead:
        tenant_id = self._require_tenant_id(context)
        return await self._question_response(tenant_id, question_id)

    async def update_question(
        self,
        context: TenantContext,
        principal: Principal,
        question_id: uuid.UUID,
        payload: QuestionUpdate,
    ) -> QuestionRead:
        tenant_id = self._require_tenant_id(context)
        question = await self._get_question_or_raise(tenant_id, question_id)
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        option_payloads = update_data.pop("options", None)
        tag_payloads = update_data.pop("tags", None)
        requested_type = update_data.get("question_type")
        requested_marks = update_data.get("marks")
        requested_negative = update_data.get("negative_marks")
        requested_status = update_data.get("status")
        question_type = requested_type or QuestionType(question.question_type)
        marks = requested_marks or question.marks
        negative_marks = (
            requested_negative if requested_negative is not None else question.negative_marks
        )
        options_for_validation = option_payloads
        if options_for_validation is None:
            options_for_validation = [
                QuestionOptionCreate(
                    label=option.label,
                    body=option.body,
                    is_correct=option.is_correct,
                    explanation=option.explanation,
                    order_index=option.order_index,
                )
                for option in question.options
            ]
        self._validate_question_payload(
            question_type,
            marks,
            negative_marks,
            options_for_validation,
        )
        if requested_status is not None:
            self._validate_status_transition(
                QuestionStatus(question.status),
                requested_status,
            )
        if "topic_id" in update_data:
            await self._get_topic_or_raise(tenant_id, update_data["topic_id"])
        for field, value in update_data.items():
            if field == "metadata":
                question.metadata_ = value
            else:
                setattr(question, field, value.value if hasattr(value, "value") else value)
        try:
            if option_payloads is not None:
                await self._replace_options(tenant_id, question.id, option_payloads)
            if tag_payloads is not None:
                await self._replace_tags(tenant_id, question.id, tag_payloads)
            await self.session.flush()
            response = await self._question_response(tenant_id, question.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "question_conflict",
                "Question update conflicts with existing data.",
                status_code=409,
            ) from exc
        await self._publish_event("question.updated", context, principal, question.id)
        return response

    async def create_question_set(
        self,
        context: TenantContext,
        principal: Principal,
        payload: QuestionSetCreate,
    ) -> QuestionSetRead:
        tenant_id = self._require_tenant_id(context)
        question_set = QuestionSet(
            tenant_id=tenant_id,
            title=payload.title,
            description=payload.description,
            status=payload.status.value,
            created_by=principal.user_id,
        )
        try:
            await self.question_sets.add(question_set)
            await self.session.refresh(question_set)
            response = QuestionSetRead.model_validate(question_set)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "question_set_conflict",
                "Question set title already exists for this tenant.",
                status_code=409,
            ) from exc
        await self._publish_event("question_set.created", context, principal, question_set.id)
        return response

    async def list_question_sets(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor: str | None,
        status: QuestionSetStatus | None,
        search: str | None,
        sort: str,
    ) -> QuestionSetPage:
        tenant_id = self._require_tenant_id(context)
        result = await self.question_sets.list_for_tenant(
            tenant_id,
            limit=limit,
            cursor=cursor,
            status=status.value if status else None,
            search=search,
            sort=sort,
        )
        return QuestionSetPage(
            items=[QuestionSetRead.model_validate(item) for item in result.items],
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    async def get_question_set(
        self,
        context: TenantContext,
        question_set_id: uuid.UUID,
    ) -> QuestionSetDetailRead:
        tenant_id = self._require_tenant_id(context)
        return await self._question_set_response(tenant_id, question_set_id)

    async def add_question_set_item(
        self,
        context: TenantContext,
        principal: Principal,
        question_set_id: uuid.UUID,
        payload: QuestionSetItemCreate,
    ) -> QuestionSetDetailRead:
        tenant_id = self._require_tenant_id(context)
        question_set = await self._get_question_set_or_raise(tenant_id, question_set_id)
        question = await self._get_question_or_raise(tenant_id, payload.question_id)
        existing = await self.question_set_items.get_assignment(
            tenant_id,
            question_set.id,
            question.id,
        )
        if existing is not None:
            raise PrepSuiteError(
                "question_set_item_conflict",
                "Question is already in this question set.",
                status_code=409,
            )
        order_index = payload.order_index
        if order_index is None:
            order_index = await self.question_set_items.next_order_index(tenant_id, question_set.id)
        item = QuestionSetItem(
            tenant_id=tenant_id,
            question_set_id=question_set.id,
            question_id=question.id,
            order_index=order_index,
            marks_override=payload.marks_override,
        )
        try:
            await self.question_set_items.add(item)
            await self._recalculate_question_set(question_set)
            response = await self._question_set_response(tenant_id, question_set.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "question_set_item_conflict",
                "Question set item conflicts with an existing item.",
                status_code=409,
            ) from exc
        await self._publish_event("question_set.item_added", context, principal, item.id)
        return response

    async def reorder_question_set(
        self,
        context: TenantContext,
        principal: Principal,
        question_set_id: uuid.UUID,
        payload: QuestionSetReorderRequest,
    ) -> QuestionSetDetailRead:
        tenant_id = self._require_tenant_id(context)
        question_set = await self._get_question_set_or_raise(tenant_id, question_set_id)
        item_ids = [item.item_id for item in payload.items]
        if len(item_ids) != len(set(item_ids)):
            raise PrepSuiteError(
                "duplicate_question_set_item",
                "Question set item IDs must be unique.",
                status_code=422,
            )
        items = [
            await self._get_question_set_item_or_raise(tenant_id, item_id)
            for item_id in item_ids
        ]
        for item in items:
            if item.question_set_id != question_set.id:
                raise PrepSuiteError(
                    "question_set_item_not_found",
                    "Question set item was not found.",
                    status_code=404,
                )
        for index, item in enumerate(items, start=1):
            item.order_index = 100000 + index
        await self.session.flush()
        item_by_id = {item.id: item for item in items}
        for reorder_item in payload.items:
            item_by_id[reorder_item.item_id].order_index = reorder_item.order_index
        await self.session.flush()
        response = await self._question_set_response(tenant_id, question_set.id)
        await self.session.commit()
        await self._publish_event("question_set.reordered", context, principal, question_set.id)
        return response

    async def remove_question_set_item(
        self,
        context: TenantContext,
        principal: Principal,
        question_set_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> QuestionSetDetailRead:
        tenant_id = self._require_tenant_id(context)
        question_set = await self._get_question_set_or_raise(tenant_id, question_set_id)
        item = await self._get_question_set_item_or_raise(tenant_id, item_id)
        if item.question_set_id != question_set.id:
            raise PrepSuiteError(
                "question_set_item_not_found",
                "Question set item was not found.",
                status_code=404,
            )
        await self.session.delete(item)
        await self.session.flush()
        await self._recalculate_question_set(question_set)
        response = await self._question_set_response(tenant_id, question_set.id)
        await self.session.commit()
        await self._publish_event("question_set.item_removed", context, principal, item_id)
        return response

    async def create_ai_generation_job(
        self,
        context: TenantContext,
        principal: Principal,
        payload: AIQuestionGenerationJobCreate,
    ) -> AIQuestionGenerationJobRead:
        tenant_id = self._require_tenant_id(context)
        output = self.generation_provider.generate(payload)
        job = AIQuestionGenerationJob(
            tenant_id=tenant_id,
            requested_by=principal.user_id,
            prompt=payload.prompt,
            topic=payload.topic,
            difficulty=payload.difficulty.value,
            question_type=payload.question_type.value,
            count=payload.count,
            status=AIGenerationJobStatus.COMPLETED.value,
            output=output,
        )
        await self.ai_jobs.add(job)
        await self.session.refresh(job)
        response = AIQuestionGenerationJobRead.model_validate(job)
        await self.session.commit()
        await self._publish_event("question.ai_generation.completed", context, principal, job.id)
        return response

    async def get_ai_generation_job(
        self,
        context: TenantContext,
        job_id: uuid.UUID,
    ) -> AIQuestionGenerationJobRead:
        tenant_id = self._require_tenant_id(context)
        job = await self._get_ai_job_or_raise(tenant_id, job_id)
        return AIQuestionGenerationJobRead.model_validate(job)

    async def approve_ai_generation_job(
        self,
        context: TenantContext,
        principal: Principal,
        job_id: uuid.UUID,
        payload: AIQuestionGenerationApproveRequest,
    ) -> AIQuestionGenerationApprovalRead:
        tenant_id = self._require_tenant_id(context)
        job = await self._get_ai_job_or_raise(tenant_id, job_id)
        if job.status == AIGenerationJobStatus.APPROVED.value or job.reviewed_at is not None:
            raise PrepSuiteError(
                "ai_generation_already_reviewed",
                "AI generation job has already been reviewed.",
                status_code=409,
            )
        if job.status != AIGenerationJobStatus.COMPLETED.value:
            raise PrepSuiteError(
                "ai_generation_not_ready",
                "AI generation job is not ready for approval.",
                status_code=409,
            )
        topic = await self._resolve_ai_approval_topic(tenant_id, job, payload.topic_id)
        candidates = list(job.output.get("questions", []))
        selected_indexes = payload.selected_indexes or list(range(len(candidates)))
        if not selected_indexes:
            raise PrepSuiteError(
                "ai_generation_selection_required",
                "At least one generated question must be selected.",
                status_code=422,
            )
        created_ids: list[uuid.UUID] = []
        for selected_index in selected_indexes:
            try:
                candidate = candidates[selected_index]
            except IndexError as exc:
                raise PrepSuiteError(
                    "ai_generation_selection_invalid",
                    "Selected generated question index is invalid.",
                    status_code=422,
                    details={"index": selected_index},
                ) from exc
            created = await self._create_question_from_ai_candidate(
                tenant_id,
                principal,
                job,
                topic.id,
                candidate,
                payload.status,
            )
            created_ids.append(created.id)
        job.status = AIGenerationJobStatus.APPROVED.value
        job.reviewed_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(job)
        questions = [
            await self._question_response(tenant_id, question_id)
            for question_id in created_ids
        ]
        job_response = AIQuestionGenerationJobRead.model_validate(job)
        await self.session.commit()
        await self._publish_event("question.ai_generation.approved", context, principal, job.id)
        return AIQuestionGenerationApprovalRead(job=job_response, questions=questions)

    async def _create_question_from_ai_candidate(
        self,
        tenant_id: uuid.UUID,
        principal: Principal,
        job: AIQuestionGenerationJob,
        topic_id: uuid.UUID,
        candidate: dict[str, Any],
        status: QuestionStatus,
    ) -> Question:
        options = [
            QuestionOptionCreate.model_validate(option)
            for option in candidate.get("options", [])
        ]
        marks = Decimal(str(candidate.get("marks", "1.00")))
        negative_marks = Decimal(str(candidate.get("negative_marks", "0.00")))
        question_type = QuestionType(job.question_type)
        self._validate_question_payload(question_type, marks, negative_marks, options)
        metadata = dict(candidate.get("metadata", {}))
        metadata.update({"ai_generation_job_id": str(job.id), "source": "ai_generation"})
        question = Question(
            tenant_id=tenant_id,
            topic_id=topic_id,
            question_type=job.question_type,
            difficulty=job.difficulty,
            body=str(candidate.get("body", job.prompt)),
            explanation=candidate.get("explanation"),
            marks=marks,
            negative_marks=negative_marks,
            metadata_=metadata,
            status=status.value,
            created_by=principal.user_id,
        )
        await self.questions.add(question)
        await self._replace_options(tenant_id, question.id, options)
        await self._replace_tags(
            tenant_id,
            question.id,
            normalize_tags(list(candidate.get("tags", []))),
        )
        return question

    async def _resolve_ai_approval_topic(
        self,
        tenant_id: uuid.UUID,
        job: AIQuestionGenerationJob,
        topic_id: uuid.UUID | None,
    ) -> QuestionTopic:
        if topic_id is not None:
            return await self._get_topic_or_raise(tenant_id, topic_id)
        slug = slugify(job.topic)
        existing = await self.topics.get_by_slug(tenant_id, slug)
        if existing is not None:
            return existing
        topic = QuestionTopic(
            tenant_id=tenant_id,
            name=job.topic,
            slug=slug,
            status=TopicStatus.ACTIVE.value,
        )
        await self.topics.add(topic)
        return topic

    async def _replace_options(
        self,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
        option_payloads: list[QuestionOptionCreate],
    ) -> None:
        await self.session.execute(
            delete(QuestionOption).where(
                QuestionOption.tenant_id == tenant_id,
                QuestionOption.question_id == question_id,
            )
        )
        for index, option_payload in enumerate(option_payloads, start=1):
            self.session.add(
                QuestionOption(
                    tenant_id=tenant_id,
                    question_id=question_id,
                    label=option_payload.label,
                    body=option_payload.body,
                    is_correct=option_payload.is_correct,
                    explanation=option_payload.explanation,
                    order_index=option_payload.order_index or index,
                )
            )

    async def _replace_tags(
        self,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
        tag_payloads: list[str],
    ) -> None:
        await self.session.execute(
            delete(QuestionTag).where(
                QuestionTag.tenant_id == tenant_id,
                QuestionTag.question_id == question_id,
            )
        )
        for tag in normalize_tags(tag_payloads):
            self.session.add(QuestionTag(tenant_id=tenant_id, question_id=question_id, name=tag))

    async def _recalculate_question_set(self, question_set: QuestionSet) -> None:
        items = await self.question_set_items.list_for_set(question_set.tenant_id, question_set.id)
        total = Decimal("0.00")
        difficulty_counts: Counter[str] = Counter()
        topic_counts: Counter[str] = Counter()
        for item in items:
            marks = item.marks_override if item.marks_override is not None else item.question.marks
            total += marks
            difficulty_counts[item.question.difficulty] += 1
            topic_counts[str(item.question.topic_id)] += 1
        question_set.total_marks = total
        question_set.difficulty_distribution = dict(difficulty_counts)
        question_set.topic_distribution = dict(topic_counts)

    def _validate_question_payload(
        self,
        question_type: QuestionType,
        marks: Decimal,
        negative_marks: Decimal,
        options: list[QuestionOptionCreate],
    ) -> None:
        if negative_marks > marks:
            raise PrepSuiteError(
                "invalid_question_marks",
                "Negative marks cannot exceed marks.",
                status_code=422,
            )
        correct_count = sum(1 for option in options if option.is_correct)
        if question_type == QuestionType.MCQ:
            if len(options) < 2 or correct_count != 1:
                raise PrepSuiteError(
                    "invalid_question_options",
                    "MCQ questions require at least two options and exactly one correct option.",
                    status_code=422,
                )
        elif question_type == QuestionType.TRUE_FALSE:
            if len(options) != 2 or correct_count != 1:
                raise PrepSuiteError(
                    "invalid_question_options",
                    "True/false questions require exactly two options and one correct option.",
                    status_code=422,
                )
        elif question_type == QuestionType.MULTI_SELECT:
            if len(options) < 2 or correct_count < 1:
                raise PrepSuiteError(
                    "invalid_question_options",
                    "Multi-select questions require at least two options and one correct option.",
                    status_code=422,
                )
        elif question_type in OPTIONLESS_TYPES and options:
            raise PrepSuiteError(
                "invalid_question_options",
                "This question type does not accept options.",
                status_code=422,
            )
        for index, option in enumerate(options, start=1):
            if option.order_index is not None and option.order_index == 0:
                raise PrepSuiteError(
                    "invalid_option_order",
                    "Option order indexes must be positive when provided.",
                    status_code=422,
                    details={"option_index": index},
                )

    def _validate_status_transition(
        self,
        current_status: QuestionStatus,
        requested_status: QuestionStatus,
    ) -> None:
        if requested_status not in ALLOWED_STATUS_TRANSITIONS[current_status]:
            raise PrepSuiteError(
                "invalid_question_status_transition",
                "Question status transition is not allowed.",
                status_code=409,
                details={"from": current_status.value, "to": requested_status.value},
            )

    async def _get_topic_or_raise(
        self,
        tenant_id: uuid.UUID,
        topic_id: uuid.UUID,
    ) -> QuestionTopic:
        topic = await self.topics.get_for_tenant(tenant_id, topic_id)
        if topic is None:
            raise PrepSuiteError(
                "question_topic_not_found",
                "Question topic was not found.",
                status_code=404,
            )
        return topic

    async def _get_question_or_raise(
        self,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> Question:
        question = await self.questions.get_for_tenant(tenant_id, question_id)
        if question is None:
            raise PrepSuiteError("question_not_found", "Question was not found.", status_code=404)
        return question

    async def _get_question_set_or_raise(
        self,
        tenant_id: uuid.UUID,
        question_set_id: uuid.UUID,
    ) -> QuestionSet:
        question_set = await self.question_sets.get_for_tenant(tenant_id, question_set_id)
        if question_set is None:
            raise PrepSuiteError(
                "question_set_not_found",
                "Question set was not found.",
                status_code=404,
            )
        return question_set

    async def _get_question_set_item_or_raise(
        self,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> QuestionSetItem:
        item = await self.question_set_items.get_for_tenant(tenant_id, item_id)
        if item is None:
            raise PrepSuiteError(
                "question_set_item_not_found",
                "Question set item was not found.",
                status_code=404,
            )
        return item

    async def _get_ai_job_or_raise(
        self,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> AIQuestionGenerationJob:
        job = await self.ai_jobs.get_for_tenant(tenant_id, job_id)
        if job is None:
            raise PrepSuiteError(
                "ai_generation_job_not_found",
                "AI generation job was not found.",
                status_code=404,
            )
        return job

    async def _question_response(
        self,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> QuestionRead:
        question = await self._get_question_or_raise(tenant_id, question_id)
        return self._question_read(question)

    async def _question_set_response(
        self,
        tenant_id: uuid.UUID,
        question_set_id: uuid.UUID,
    ) -> QuestionSetDetailRead:
        question_set = await self.question_sets.detail(tenant_id, question_set_id)
        if question_set is None:
            raise PrepSuiteError(
                "question_set_not_found",
                "Question set was not found.",
                status_code=404,
            )
        items = sorted(question_set.items, key=lambda item: (item.order_index, item.id))
        return QuestionSetDetailRead(
            question_set=QuestionSetRead.model_validate(question_set),
            items=[self._question_set_item_read(item) for item in items],
        )

    def _question_read(self, question: Question) -> QuestionRead:
        return QuestionRead.model_validate(
            {
                "id": question.id,
                "tenant_id": question.tenant_id,
                "topic_id": question.topic_id,
                "question_type": QuestionType(question.question_type),
                "difficulty": QuestionDifficulty(question.difficulty),
                "bloom_level": question.bloom_level,
                "body": question.body,
                "explanation": question.explanation,
                "marks": question.marks,
                "negative_marks": question.negative_marks,
                "metadata_": question.metadata_,
                "status": QuestionStatus(question.status),
                "created_by": question.created_by,
                "options": [
                    QuestionOptionRead.model_validate(option)
                    for option in sorted(
                        question.options,
                        key=lambda item: (item.order_index, item.id),
                    )
                ],
                "tags": [tag.name for tag in sorted(question.tags, key=lambda item: item.name)],
                "created_at": question.created_at,
                "updated_at": question.updated_at,
                "deleted_at": question.deleted_at,
            }
        )

    def _question_set_item_read(self, item: QuestionSetItem) -> QuestionSetItemRead:
        return QuestionSetItemRead(
            id=item.id,
            tenant_id=item.tenant_id,
            question_set_id=item.question_set_id,
            question_id=item.question_id,
            order_index=item.order_index,
            marks_override=item.marks_override,
            question=self._question_read(item.question),
            created_at=item.created_at,
            updated_at=item.updated_at,
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
