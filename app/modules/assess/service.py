from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import DomainEvent, EventDispatcher, event_dispatcher
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.tenant_context import TenantContext
from app.modules.assess.enums import (
    AnswerEvaluationStatus,
    AssessmentStatus,
    AssessmentType,
    AttemptStatus,
    ResultStatus,
)
from app.modules.assess.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentEvaluation,
    AssessmentQuestion,
    AssessmentResult,
    AssessmentSection,
    EvaluationComment,
)
from app.modules.assess.repository import (
    AssessmentAnswerRepository,
    AssessmentAttemptRepository,
    AssessmentQuestionRepository,
    AssessmentRepository,
    AssessmentResultRepository,
    AssessmentSectionRepository,
)
from app.modules.assess.schemas import (
    AnswerRead,
    AnswerSubmitRequest,
    AssessmentAnalyticsRead,
    AssessmentCreate,
    AssessmentDetailRead,
    AssessmentPage,
    AssessmentPublishRequest,
    AssessmentQuestionRead,
    AssessmentRead,
    AssessmentScheduleRequest,
    AssessmentSectionRead,
    AssessmentUpdate,
    AttemptRead,
    AttemptStartRequest,
    AttemptSubmitRequest,
    EvaluationQueueItemRead,
    ManualEvaluateAnswerRequest,
    ResultRead,
    ResultsPublishRead,
)
from app.modules.learn.models import Course
from app.modules.question.enums import QuestionType
from app.modules.question.models import Question
from app.modules.question.repository import QuestionSetRepository
from app.modules.question.schemas import QuestionOptionRead, QuestionRead
from app.modules.students.models import Batch, BatchStudent, Student

AUTO_EVALUATED_TYPES = {
    QuestionType.MCQ.value,
    QuestionType.MULTI_SELECT.value,
    QuestionType.TRUE_FALSE.value,
}
TERMINAL_ATTEMPT_STATUSES = {
    AttemptStatus.SUBMITTED.value,
    AttemptStatus.AUTO_SUBMITTED.value,
    AttemptStatus.EVALUATED.value,
}


class PrepAssessService:
    def __init__(
        self,
        session: AsyncSession,
        dispatcher: EventDispatcher = event_dispatcher,
    ) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.assessments = AssessmentRepository(session)
        self.sections = AssessmentSectionRepository(session)
        self.questions = AssessmentQuestionRepository(session)
        self.attempts = AssessmentAttemptRepository(session)
        self.answers = AssessmentAnswerRepository(session)
        self.results = AssessmentResultRepository(session)
        self.question_sets = QuestionSetRepository(session)

    async def create_assessment(
        self,
        context: TenantContext,
        principal: Principal,
        payload: AssessmentCreate,
    ) -> AssessmentDetailRead:
        tenant_id = self._require_tenant_id(context)
        await self._validate_optional_course(tenant_id, payload.course_id)
        await self._validate_optional_batch(tenant_id, payload.batch_id)
        question_set = None
        if payload.question_set_id is not None:
            question_set = await self.question_sets.detail(tenant_id, payload.question_set_id)
            if question_set is None:
                raise PrepSuiteError(
                    "question_set_not_found",
                    "Question set was not found.",
                    status_code=404,
                )
            if not question_set.items:
                raise PrepSuiteError(
                    "question_set_empty",
                    "Question set must contain at least one question.",
                    status_code=422,
                )
        assessment = Assessment(
            tenant_id=tenant_id,
            course_id=payload.course_id,
            batch_id=payload.batch_id,
            question_set_id=payload.question_set_id,
            title=payload.title,
            type=payload.type.value,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            duration_minutes=payload.duration_minutes,
            settings=payload.settings,
            created_by=principal.user_id,
        )
        try:
            await self.assessments.add(assessment)
            if question_set is not None:
                section = AssessmentSection(
                    tenant_id=tenant_id,
                    assessment_id=assessment.id,
                    title="Default Section",
                    order_index=1,
                    total_marks=question_set.total_marks,
                )
                await self.sections.add(section)
                for item in sorted(question_set.items, key=lambda set_item: set_item.order_index):
                    marks = item.marks_override or item.question.marks
                    self.session.add(
                        AssessmentQuestion(
                            tenant_id=tenant_id,
                            assessment_id=assessment.id,
                            section_id=section.id,
                            question_id=item.question_id,
                            order_index=item.order_index,
                            marks=marks,
                            negative_marks=item.question.negative_marks,
                            metadata_={"question_set_item_id": str(item.id)},
                        )
                    )
                assessment.total_marks = question_set.total_marks
                await self.session.flush()
            response = await self._assessment_detail_response(tenant_id, assessment.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "assessment_conflict",
                "Assessment could not be created due to conflicting data.",
                status_code=409,
            ) from exc
        await self._publish_event("assessment.created", context, principal, assessment.id)
        return response

    async def list_assessments(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor: str | None,
        status: AssessmentStatus | None,
        assessment_type: AssessmentType | None,
        course_id: uuid.UUID | None,
        batch_id: uuid.UUID | None,
        search: str | None,
        sort: str,
    ) -> AssessmentPage:
        tenant_id = self._require_tenant_id(context)
        result = await self.assessments.list_for_tenant(
            tenant_id,
            limit=limit,
            cursor=cursor,
            status=status.value if status else None,
            assessment_type=assessment_type.value if assessment_type else None,
            course_id=course_id,
            batch_id=batch_id,
            search=search,
            sort=sort,
        )
        return AssessmentPage(
            items=[AssessmentRead.model_validate(item) for item in result.items],
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    async def get_assessment(
        self,
        context: TenantContext,
        assessment_id: uuid.UUID,
    ) -> AssessmentDetailRead:
        tenant_id = self._require_tenant_id(context)
        return await self._assessment_detail_response(tenant_id, assessment_id)

    async def update_assessment(
        self,
        context: TenantContext,
        principal: Principal,
        assessment_id: uuid.UUID,
        payload: AssessmentUpdate,
    ) -> AssessmentRead:
        tenant_id = self._require_tenant_id(context)
        assessment = await self._get_assessment_or_raise(tenant_id, assessment_id)
        if assessment.status not in {
            AssessmentStatus.DRAFT.value,
            AssessmentStatus.SCHEDULED.value,
        }:
            raise PrepSuiteError(
                "assessment_locked",
                "Only draft or scheduled assessments can be updated.",
                status_code=409,
            )
        update_data = payload.model_dump(exclude_unset=True, mode="python")
        if "course_id" in update_data:
            await self._validate_optional_course(tenant_id, update_data["course_id"])
        if "batch_id" in update_data:
            await self._validate_optional_batch(tenant_id, update_data["batch_id"])
        for field, value in update_data.items():
            setattr(assessment, field, value)
        await self.session.flush()
        await self.session.refresh(assessment)
        response = AssessmentRead.model_validate(assessment)
        await self.session.commit()
        await self._publish_event("assessment.updated", context, principal, assessment.id)
        return response

    async def schedule_assessment(
        self,
        context: TenantContext,
        principal: Principal,
        assessment_id: uuid.UUID,
        payload: AssessmentScheduleRequest,
    ) -> AssessmentRead:
        tenant_id = self._require_tenant_id(context)
        assessment = await self._get_assessment_or_raise(tenant_id, assessment_id)
        if not await self.questions.list_for_assessment(tenant_id, assessment.id):
            raise PrepSuiteError(
                "assessment_has_no_questions",
                "Assessment must have questions before scheduling.",
                status_code=409,
            )
        assessment.starts_at = payload.starts_at
        assessment.ends_at = payload.ends_at
        assessment.duration_minutes = payload.duration_minutes or assessment.duration_minutes
        assessment.status = AssessmentStatus.SCHEDULED.value
        await self.session.flush()
        await self.session.refresh(assessment)
        response = AssessmentRead.model_validate(assessment)
        await self.session.commit()
        await self._publish_event("assessment.scheduled", context, principal, assessment.id)
        return response

    async def publish_assessment(
        self,
        context: TenantContext,
        principal: Principal,
        assessment_id: uuid.UUID,
        payload: AssessmentPublishRequest,
    ) -> AssessmentRead:
        tenant_id = self._require_tenant_id(context)
        assessment = await self._get_assessment_or_raise(tenant_id, assessment_id)
        if assessment.status not in {
            AssessmentStatus.DRAFT.value,
            AssessmentStatus.SCHEDULED.value,
            AssessmentStatus.LIVE.value,
        }:
            raise PrepSuiteError(
                "assessment_publish_not_allowed",
                "Assessment cannot be published to learners in its current state.",
                status_code=409,
            )
        if not payload.force and (assessment.starts_at is None or assessment.ends_at is None):
            raise PrepSuiteError(
                "assessment_schedule_required",
                "Schedule the assessment before publishing it.",
                status_code=409,
            )
        assessment.status = AssessmentStatus.LIVE.value
        assessment.published_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(assessment)
        response = AssessmentRead.model_validate(assessment)
        await self.session.commit()
        await self._publish_event("assessment.published", context, principal, assessment.id)
        return response

    async def start_attempt(
        self,
        context: TenantContext,
        principal: Principal,
        assessment_id: uuid.UUID,
        payload: AttemptStartRequest,
    ) -> AttemptRead:
        tenant_id = self._require_tenant_id(context)
        assessment = await self._get_assessment_or_raise(tenant_id, assessment_id)
        self._assert_attempt_window(assessment)
        await self._validate_student_access(tenant_id, assessment, payload.student_id)
        existing = await self.attempts.get_for_student(tenant_id, assessment.id, payload.student_id)
        if existing is not None:
            return self._attempt_read(existing)
        attempt = AssessmentAttempt(
            tenant_id=tenant_id,
            assessment_id=assessment.id,
            student_id=payload.student_id,
            metadata_={"start_idempotency_key": payload.idempotency_key}
            if payload.idempotency_key
            else {},
        )
        try:
            await self.attempts.add(attempt)
            await self.session.refresh(attempt)
            response = self._attempt_read(attempt)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "assessment_attempt_conflict",
                "Assessment attempt already exists for this student.",
                status_code=409,
            ) from exc
        await self._publish_event("assessment.attempt.started", context, principal, attempt.id)
        return response

    async def submit_answer(
        self,
        context: TenantContext,
        principal: Principal,
        attempt_id: uuid.UUID,
        payload: AnswerSubmitRequest,
    ) -> AnswerRead:
        tenant_id = self._require_tenant_id(context)
        attempt = await self._get_attempt_or_raise(tenant_id, attempt_id)
        if attempt.status != AttemptStatus.STARTED.value:
            raise PrepSuiteError(
                "attempt_not_open",
                "Answers can only be submitted while an attempt is open.",
                status_code=409,
            )
        assessment_question = await self._get_assessment_question_or_raise(
            tenant_id,
            payload.assessment_question_id,
        )
        if assessment_question.assessment_id != attempt.assessment_id:
            raise PrepSuiteError(
                "assessment_question_not_found",
                "Assessment question was not found for this attempt.",
                status_code=404,
            )
        existing = await self.answers.get_for_attempt_question(
            tenant_id,
            attempt.id,
            assessment_question.id,
        )
        if existing is not None:
            if payload.idempotency_key and existing.idempotency_key == payload.idempotency_key:
                return AnswerRead.model_validate(existing)
            raise PrepSuiteError(
                "answer_already_submitted",
                "This assessment question already has an answer.",
                status_code=409,
            )
        answer = AssessmentAnswer(
            tenant_id=tenant_id,
            attempt_id=attempt.id,
            assessment_question_id=assessment_question.id,
            question_id=assessment_question.question_id,
            answer=payload.answer,
            idempotency_key=payload.idempotency_key,
        )
        await self._auto_evaluate_if_possible(answer, assessment_question)
        await self.answers.add(answer)
        await self.session.refresh(answer)
        response = AnswerRead.model_validate(answer)
        await self.session.commit()
        await self._publish_event("assessment.answer.submitted", context, principal, answer.id)
        return response

    async def submit_attempt(
        self,
        context: TenantContext,
        principal: Principal,
        attempt_id: uuid.UUID,
        payload: AttemptSubmitRequest,
    ) -> AttemptRead:
        tenant_id = self._require_tenant_id(context)
        attempt = await self._get_attempt_or_raise(tenant_id, attempt_id)
        if attempt.status in TERMINAL_ATTEMPT_STATUSES:
            return self._attempt_read(attempt)
        assessment_questions = await self.questions.list_for_assessment(
            tenant_id,
            attempt.assessment_id,
        )
        if not attempt.answers:
            raise PrepSuiteError(
                "attempt_has_no_answers",
                "At least one answer is required before submission.",
                status_code=409,
            )
        now = datetime.now(UTC)
        attempt.submitted_at = now
        if payload.idempotency_key:
            attempt.metadata_ = {
                **attempt.metadata_,
                "submit_idempotency_key": payload.idempotency_key,
            }
        if payload.auto_submit:
            attempt.status = AttemptStatus.AUTO_SUBMITTED.value
        else:
            attempt.status = AttemptStatus.SUBMITTED.value
        if self._all_answers_evaluated(assessment_questions, attempt.answers):
            await self._finalize_attempt(attempt, evaluator_user_id=None)
        await self.session.flush()
        await self.session.refresh(attempt)
        response = self._attempt_read(attempt)
        await self.session.commit()
        await self._publish_event("assessment.attempt.submitted", context, principal, attempt.id)
        return response

    async def evaluation_queue(
        self,
        context: TenantContext,
        assessment_id: uuid.UUID,
    ) -> list[EvaluationQueueItemRead]:
        tenant_id = self._require_tenant_id(context)
        await self._get_assessment_or_raise(tenant_id, assessment_id)
        pending = await self.answers.pending_for_assessment(tenant_id, assessment_id)
        queue: list[EvaluationQueueItemRead] = []
        for answer in pending:
            assessment_question = await self._get_assessment_question_or_raise(
                tenant_id,
                answer.assessment_question_id,
            )
            attempt = await self._get_attempt_or_raise(tenant_id, answer.attempt_id)
            queue.append(
                EvaluationQueueItemRead(
                    answer=AnswerRead.model_validate(answer),
                    assessment_question=await self._assessment_question_read(assessment_question),
                    attempt=self._attempt_read(attempt),
                )
            )
        return queue

    async def evaluate_answer(
        self,
        context: TenantContext,
        principal: Principal,
        answer_id: uuid.UUID,
        payload: ManualEvaluateAnswerRequest,
    ) -> AnswerRead:
        tenant_id = self._require_tenant_id(context)
        answer = await self._get_answer_or_raise(tenant_id, answer_id)
        assessment_question = await self._get_assessment_question_or_raise(
            tenant_id,
            answer.assessment_question_id,
        )
        if payload.score > assessment_question.marks:
            raise PrepSuiteError(
                "score_exceeds_marks",
                "Evaluation score cannot exceed question marks.",
                status_code=422,
            )
        answer.score = payload.score
        answer.status = AnswerEvaluationStatus.MANUAL_EVALUATED.value
        answer.evaluated_by = principal.user_id
        answer.evaluated_at = datetime.now(UTC)
        if payload.comment:
            self.session.add(
                EvaluationComment(
                    tenant_id=tenant_id,
                    answer_id=answer.id,
                    author_user_id=principal.user_id,
                    comment=payload.comment,
                    visibility="student",
                )
            )
        attempt = await self._get_attempt_or_raise(tenant_id, answer.attempt_id)
        assessment_questions = await self.questions.list_for_assessment(
            tenant_id,
            attempt.assessment_id,
        )
        if attempt.status in {
            AttemptStatus.SUBMITTED.value,
            AttemptStatus.AUTO_SUBMITTED.value,
        } and self._all_answers_evaluated(assessment_questions, attempt.answers):
            await self._finalize_attempt(attempt, evaluator_user_id=principal.user_id)
        await self.session.flush()
        await self.session.refresh(answer)
        response = AnswerRead.model_validate(answer)
        await self.session.commit()
        await self._publish_event("assessment.answer.evaluated", context, principal, answer.id)
        return response

    async def publish_results(
        self,
        context: TenantContext,
        principal: Principal,
        assessment_id: uuid.UUID,
    ) -> ResultsPublishRead:
        tenant_id = self._require_tenant_id(context)
        assessment = await self._get_assessment_or_raise(tenant_id, assessment_id)
        results = await self.results.list_for_assessment(tenant_id, assessment.id)
        if not results:
            raise PrepSuiteError(
                "assessment_results_not_ready",
                "No evaluated results are available to publish.",
                status_code=409,
            )
        now = datetime.now(UTC)
        for result in results:
            result.status = ResultStatus.PUBLISHED.value
            result.published_at = now
        assessment.status = AssessmentStatus.PUBLISHED.value
        await self.session.flush()
        await self.session.refresh(assessment)
        for result in results:
            await self.session.refresh(result)
        response = ResultsPublishRead(
            assessment=AssessmentRead.model_validate(assessment),
            results=[self._result_read(result) for result in results],
        )
        await self.session.commit()
        await self._publish_event("assessment.results.published", context, principal, assessment.id)
        return response

    async def analytics(
        self,
        context: TenantContext,
        assessment_id: uuid.UUID,
    ) -> AssessmentAnalyticsRead:
        tenant_id = self._require_tenant_id(context)
        assessment = await self._get_assessment_or_raise(tenant_id, assessment_id)
        attempts = await self.attempts.list_for_assessment(tenant_id, assessment.id)
        results = await self.results.list_for_assessment(tenant_id, assessment.id)
        scores = [result.score for result in results]
        published_count = sum(
            1 for result in results if result.status == ResultStatus.PUBLISHED.value
        )
        return AssessmentAnalyticsRead(
            assessment_id=assessment.id,
            total_marks=assessment.total_marks,
            attempts_started=len(attempts),
            attempts_submitted=sum(
                1 for attempt in attempts if attempt.status in TERMINAL_ATTEMPT_STATUSES
            ),
            attempts_evaluated=sum(
                1 for attempt in attempts if attempt.status == AttemptStatus.EVALUATED.value
            ),
            results_published=published_count,
            average_score=self._decimal_average(scores),
            highest_score=max(scores) if scores else None,
            lowest_score=min(scores) if scores else None,
        )

    async def _auto_evaluate_if_possible(
        self,
        answer: AssessmentAnswer,
        assessment_question: AssessmentQuestion,
    ) -> None:
        question = await self._get_question_with_options(
            assessment_question.tenant_id,
            assessment_question.question_id,
        )
        if question.question_type not in AUTO_EVALUATED_TYPES:
            answer.status = AnswerEvaluationStatus.PENDING.value
            return
        correct_option_ids = {
            str(option.id)
            for option in question.options
            if option.is_correct
        }
        submitted_option_ids = {
            str(option_id)
            for option_id in answer.answer.get("option_ids", [])
        }
        is_correct = submitted_option_ids == correct_option_ids
        answer.is_correct = is_correct
        answer.score = (
            assessment_question.marks
            if is_correct
            else -assessment_question.negative_marks
        )
        answer.status = AnswerEvaluationStatus.AUTO_EVALUATED.value
        answer.evaluated_at = datetime.now(UTC)

    async def _finalize_attempt(
        self,
        attempt: AssessmentAttempt,
        *,
        evaluator_user_id: uuid.UUID | None,
    ) -> None:
        assessment = await self._get_assessment_or_raise(attempt.tenant_id, attempt.assessment_id)
        total_score = sum(
            (answer.score or Decimal("0.00") for answer in attempt.answers),
            Decimal("0.00"),
        )
        attempt.score = total_score
        attempt.status = AttemptStatus.EVALUATED.value
        evaluation = AssessmentEvaluation(
            tenant_id=attempt.tenant_id,
            attempt_id=attempt.id,
            evaluated_by=evaluator_user_id,
            status=AttemptStatus.EVALUATED.value,
            total_score=total_score,
            evaluated_at=datetime.now(UTC),
            metadata_={},
        )
        self.session.add(evaluation)
        existing_result = await self.results.get_for_attempt(attempt.tenant_id, attempt.id)
        percentage = self._percentage(total_score, assessment.total_marks)
        if existing_result is None:
            self.session.add(
                AssessmentResult(
                    tenant_id=attempt.tenant_id,
                    assessment_id=attempt.assessment_id,
                    student_id=attempt.student_id,
                    attempt_id=attempt.id,
                    score=total_score,
                    percentage=percentage,
                )
            )
        else:
            existing_result.score = total_score
            existing_result.percentage = percentage

    def _all_answers_evaluated(
        self,
        assessment_questions: list[AssessmentQuestion],
        answers: list[AssessmentAnswer],
    ) -> bool:
        answer_by_question = {answer.assessment_question_id: answer for answer in answers}
        if len(answer_by_question) < len(assessment_questions):
            return False
        return all(
            answer.status
            in {
                AnswerEvaluationStatus.AUTO_EVALUATED.value,
                AnswerEvaluationStatus.MANUAL_EVALUATED.value,
            }
            for answer in answer_by_question.values()
        )

    def _assert_attempt_window(self, assessment: Assessment) -> None:
        if assessment.status not in {AssessmentStatus.SCHEDULED.value, AssessmentStatus.LIVE.value}:
            raise PrepSuiteError(
                "assessment_not_available",
                "Assessment is not available for attempts.",
                status_code=409,
            )
        now = datetime.now(UTC)
        if assessment.starts_at is not None and now < assessment.starts_at:
            raise PrepSuiteError(
                "assessment_not_started",
                "Assessment has not started yet.",
                status_code=409,
            )
        if assessment.ends_at is not None and now > assessment.ends_at:
            raise PrepSuiteError(
                "assessment_ended",
                "Assessment attempt window has ended.",
                status_code=409,
            )

    async def _validate_student_access(
        self,
        tenant_id: uuid.UUID,
        assessment: Assessment,
        student_id: uuid.UUID,
    ) -> None:
        statement = select(Student.id).where(
            Student.tenant_id == tenant_id,
            Student.id == student_id,
            Student.deleted_at.is_(None),
        )
        if await self.session.scalar(statement) is None:
            raise PrepSuiteError("student_not_found", "Student was not found.", status_code=404)
        if assessment.batch_id is None:
            return
        membership = await self.session.scalar(
            select(BatchStudent.id).where(
                BatchStudent.tenant_id == tenant_id,
                BatchStudent.batch_id == assessment.batch_id,
                BatchStudent.student_id == student_id,
                BatchStudent.status == "active",
            )
        )
        if membership is None:
            raise PrepSuiteError(
                "student_not_in_batch",
                "Student does not belong to the assessment batch.",
                status_code=403,
            )

    async def _validate_optional_course(
        self,
        tenant_id: uuid.UUID,
        course_id: uuid.UUID | None,
    ) -> None:
        if course_id is None:
            return
        exists = await self.session.scalar(
            select(Course.id).where(
                Course.tenant_id == tenant_id,
                Course.id == course_id,
                Course.deleted_at.is_(None),
            )
        )
        if exists is None:
            raise PrepSuiteError("course_not_found", "Course was not found.", status_code=404)

    async def _validate_optional_batch(
        self,
        tenant_id: uuid.UUID,
        batch_id: uuid.UUID | None,
    ) -> None:
        if batch_id is None:
            return
        exists = await self.session.scalar(
            select(Batch.id).where(
                Batch.tenant_id == tenant_id,
                Batch.id == batch_id,
                Batch.deleted_at.is_(None),
            )
        )
        if exists is None:
            raise PrepSuiteError("batch_not_found", "Batch was not found.", status_code=404)

    async def _get_assessment_or_raise(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> Assessment:
        assessment = await self.assessments.get_for_tenant(tenant_id, assessment_id)
        if assessment is None:
            raise PrepSuiteError(
                "assessment_not_found",
                "Assessment was not found.",
                status_code=404,
            )
        return assessment

    async def _get_attempt_or_raise(
        self,
        tenant_id: uuid.UUID,
        attempt_id: uuid.UUID,
    ) -> AssessmentAttempt:
        attempt = await self.attempts.get_for_tenant(tenant_id, attempt_id)
        if attempt is None:
            raise PrepSuiteError(
                "assessment_attempt_not_found",
                "Assessment attempt was not found.",
                status_code=404,
            )
        return attempt

    async def _get_assessment_question_or_raise(
        self,
        tenant_id: uuid.UUID,
        assessment_question_id: uuid.UUID,
    ) -> AssessmentQuestion:
        assessment_question = await self.questions.get_for_tenant(tenant_id, assessment_question_id)
        if assessment_question is None:
            raise PrepSuiteError(
                "assessment_question_not_found",
                "Assessment question was not found.",
                status_code=404,
            )
        return assessment_question

    async def _get_answer_or_raise(
        self,
        tenant_id: uuid.UUID,
        answer_id: uuid.UUID,
    ) -> AssessmentAnswer:
        answer = await self.answers.get_for_tenant(tenant_id, answer_id)
        if answer is None:
            raise PrepSuiteError(
                "assessment_answer_not_found",
                "Assessment answer was not found.",
                status_code=404,
            )
        return answer

    async def _get_question_with_options(
        self,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> Question:
        statement = (
            select(Question)
            .where(
                Question.tenant_id == tenant_id,
                Question.id == question_id,
                Question.deleted_at.is_(None),
            )
            .options(selectinload(Question.options), selectinload(Question.tags))
        )
        question = await self.session.scalar(statement)
        if question is None:
            raise PrepSuiteError("question_not_found", "Question was not found.", status_code=404)
        return question

    async def _assessment_detail_response(
        self,
        tenant_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> AssessmentDetailRead:
        assessment = await self.assessments.detail(tenant_id, assessment_id)
        if assessment is None:
            raise PrepSuiteError(
                "assessment_not_found",
                "Assessment was not found.",
                status_code=404,
            )
        sections = sorted(assessment.sections, key=lambda item: (item.order_index, item.id))
        questions = sorted(assessment.questions, key=lambda item: (item.order_index, item.id))
        return AssessmentDetailRead(
            assessment=AssessmentRead.model_validate(assessment),
            sections=[AssessmentSectionRead.model_validate(section) for section in sections],
            questions=[
                await self._assessment_question_read(assessment_question)
                for assessment_question in questions
            ],
        )

    async def _assessment_question_read(
        self,
        assessment_question: AssessmentQuestion,
    ) -> AssessmentQuestionRead:
        question = await self._get_question_with_options(
            assessment_question.tenant_id,
            assessment_question.question_id,
        )
        return AssessmentQuestionRead.model_validate(
            {
                "id": assessment_question.id,
                "tenant_id": assessment_question.tenant_id,
                "assessment_id": assessment_question.assessment_id,
                "section_id": assessment_question.section_id,
                "question_id": assessment_question.question_id,
                "order_index": assessment_question.order_index,
                "marks": assessment_question.marks,
                "negative_marks": assessment_question.negative_marks,
                "metadata_": assessment_question.metadata_,
                "question": self._question_read(question),
                "created_at": assessment_question.created_at,
                "updated_at": assessment_question.updated_at,
            }
        )

    def _question_read(self, question: Question) -> QuestionRead:
        return QuestionRead.model_validate(
            {
                "id": question.id,
                "tenant_id": question.tenant_id,
                "topic_id": question.topic_id,
                "question_type": question.question_type,
                "difficulty": question.difficulty,
                "bloom_level": question.bloom_level,
                "body": question.body,
                "explanation": question.explanation,
                "marks": question.marks,
                "negative_marks": question.negative_marks,
                "metadata_": question.metadata_,
                "status": question.status,
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

    def _attempt_read(self, attempt: AssessmentAttempt) -> AttemptRead:
        return AttemptRead.model_validate(
            {
                "id": attempt.id,
                "tenant_id": attempt.tenant_id,
                "assessment_id": attempt.assessment_id,
                "student_id": attempt.student_id,
                "status": attempt.status,
                "started_at": attempt.started_at,
                "submitted_at": attempt.submitted_at,
                "score": attempt.score,
                "metadata_": attempt.metadata_,
                "created_at": attempt.created_at,
                "updated_at": attempt.updated_at,
            }
        )

    def _result_read(self, result: AssessmentResult) -> ResultRead:
        return ResultRead.model_validate(
            {
                "id": result.id,
                "tenant_id": result.tenant_id,
                "assessment_id": result.assessment_id,
                "student_id": result.student_id,
                "attempt_id": result.attempt_id,
                "score": result.score,
                "percentage": result.percentage,
                "status": result.status,
                "published_at": result.published_at,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
            }
        )

    def _percentage(self, score: Decimal, total_marks: Decimal) -> Decimal:
        if total_marks <= 0:
            return Decimal("0.00")
        return ((score / total_marks) * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def _decimal_average(self, values: list[Decimal]) -> Decimal | None:
        if not values:
            return None
        return (sum(values, Decimal("0.00")) / Decimal(len(values))).quantize(
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
