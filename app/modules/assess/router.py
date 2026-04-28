from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gates import require_app_enabled
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.assess.enums import AssessmentStatus, AssessmentType
from app.modules.assess.schemas import (
    AnswerRead,
    AnswerSubmitRequest,
    AssessmentAnalyticsRead,
    AssessmentCreate,
    AssessmentDetailRead,
    AssessmentPage,
    AssessmentPublishRequest,
    AssessmentRead,
    AssessmentScheduleRequest,
    AssessmentUpdate,
    AttemptRead,
    AttemptStartRequest,
    AttemptSubmitRequest,
    EvaluationQueueItemRead,
    ManualEvaluateAnswerRequest,
    ResultsPublishRead,
)
from app.modules.assess.service import PrepAssessService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    tags=["PrepAssess"],
    dependencies=[Depends(require_app_enabled("prepassess"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
SearchQuery = Annotated[str | None, Query(max_length=160)]
AssessmentSortQuery = Annotated[str, Query(pattern="^(created_at|starts_at|title)$")]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.post(
    "/assessments",
    response_model=AssessmentDetailRead,
    status_code=status.HTTP_201_CREATED,
    name="prepassess:create_assessment",
    dependencies=[Depends(require_permission("prepassess.assessment.create"))],
)
async def create_assessment(
    payload: AssessmentCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).create_assessment(context, principal, payload)


@router.get(
    "/assessments",
    response_model=AssessmentPage,
    name="prepassess:list_assessments",
    dependencies=[Depends(require_permission("prepassess.assessment.read"))],
)
async def list_assessments(
    context: TenantContextDep,
    session: TenantSessionDep,
    limit: LimitQuery = 50,
    cursor: str | None = None,
    status_filter: Annotated[AssessmentStatus | None, Query(alias="status")] = None,
    assessment_type: Annotated[AssessmentType | None, Query(alias="type")] = None,
    course_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    search: SearchQuery = None,
    sort: AssessmentSortQuery = "created_at",
) -> object:
    return await PrepAssessService(session).list_assessments(
        context,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        assessment_type=assessment_type,
        course_id=course_id,
        batch_id=batch_id,
        search=search,
        sort=sort,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentDetailRead,
    name="prepassess:get_assessment",
    dependencies=[Depends(require_permission("prepassess.assessment.read"))],
)
async def get_assessment(
    assessment_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepAssessService(session).get_assessment(context, assessment_id)


@router.patch(
    "/assessments/{assessment_id}",
    response_model=AssessmentRead,
    name="prepassess:update_assessment",
    dependencies=[Depends(require_permission("prepassess.assessment.update"))],
)
async def update_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).update_assessment(
        context,
        principal,
        assessment_id,
        payload,
    )


@router.post(
    "/assessments/{assessment_id}/schedule",
    response_model=AssessmentRead,
    name="prepassess:schedule_assessment",
    dependencies=[Depends(require_permission("prepassess.assessment.schedule"))],
)
async def schedule_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentScheduleRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).schedule_assessment(
        context,
        principal,
        assessment_id,
        payload,
    )


@router.post(
    "/assessments/{assessment_id}/publish",
    response_model=AssessmentRead,
    name="prepassess:publish_assessment",
    dependencies=[Depends(require_permission("prepassess.assessment.publish"))],
)
async def publish_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentPublishRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).publish_assessment(
        context,
        principal,
        assessment_id,
        payload,
    )


@router.post(
    "/assessments/{assessment_id}/attempts/start",
    response_model=AttemptRead,
    status_code=status.HTTP_201_CREATED,
    name="prepassess:start_attempt",
    dependencies=[Depends(require_permission("prepassess.attempt.manage"))],
)
async def start_attempt(
    assessment_id: uuid.UUID,
    payload: AttemptStartRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).start_attempt(
        context,
        principal,
        assessment_id,
        payload,
    )


@router.post(
    "/assessment-attempts/{attempt_id}/answers",
    response_model=AnswerRead,
    status_code=status.HTTP_201_CREATED,
    name="prepassess:submit_answer",
    dependencies=[Depends(require_permission("prepassess.attempt.manage"))],
)
async def submit_answer(
    attempt_id: uuid.UUID,
    payload: AnswerSubmitRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).submit_answer(context, principal, attempt_id, payload)


@router.post(
    "/assessment-attempts/{attempt_id}/submit",
    response_model=AttemptRead,
    name="prepassess:submit_attempt",
    dependencies=[Depends(require_permission("prepassess.attempt.manage"))],
)
async def submit_attempt(
    attempt_id: uuid.UUID,
    payload: AttemptSubmitRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).submit_attempt(context, principal, attempt_id, payload)


@router.get(
    "/assessments/{assessment_id}/evaluation-queue",
    response_model=list[EvaluationQueueItemRead],
    name="prepassess:evaluation_queue",
    dependencies=[Depends(require_permission("prepassess.evaluation.manage"))],
)
async def evaluation_queue(
    assessment_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepAssessService(session).evaluation_queue(context, assessment_id)


@router.post(
    "/assessment-answers/{answer_id}/evaluate",
    response_model=AnswerRead,
    name="prepassess:evaluate_answer",
    dependencies=[Depends(require_permission("prepassess.evaluation.manage"))],
)
async def evaluate_answer(
    answer_id: uuid.UUID,
    payload: ManualEvaluateAnswerRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).evaluate_answer(context, principal, answer_id, payload)


@router.post(
    "/assessments/{assessment_id}/results/publish",
    response_model=ResultsPublishRead,
    name="prepassess:publish_results",
    dependencies=[Depends(require_permission("prepassess.result.publish"))],
)
async def publish_results(
    assessment_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepAssessService(session).publish_results(context, principal, assessment_id)


@router.get(
    "/assessments/{assessment_id}/analytics",
    response_model=AssessmentAnalyticsRead,
    name="prepassess:assessment_analytics",
    dependencies=[Depends(require_permission("prepassess.assessment.read"))],
)
async def assessment_analytics(
    assessment_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepAssessService(session).analytics(context, assessment_id)
