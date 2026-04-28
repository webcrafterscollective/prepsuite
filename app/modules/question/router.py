from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_gates import require_app_enabled
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import get_current_principal
from app.modules.question.enums import (
    QuestionDifficulty,
    QuestionSetStatus,
    QuestionStatus,
    QuestionType,
)
from app.modules.question.schemas import (
    AIQuestionGenerationApprovalRead,
    AIQuestionGenerationApproveRequest,
    AIQuestionGenerationJobCreate,
    AIQuestionGenerationJobRead,
    QuestionCreate,
    QuestionPage,
    QuestionRead,
    QuestionSetCreate,
    QuestionSetDetailRead,
    QuestionSetItemCreate,
    QuestionSetPage,
    QuestionSetRead,
    QuestionSetReorderRequest,
    QuestionTopicCreate,
    QuestionTopicRead,
    QuestionUpdate,
)
from app.modules.question.service import PrepQuestionService
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context

router = APIRouter(
    tags=["PrepQuestion"],
    dependencies=[Depends(require_app_enabled("prepquestion"))],
)
TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
SearchQuery = Annotated[str | None, Query(max_length=160)]
QuestionSortQuery = Annotated[str, Query(pattern="^(created_at|difficulty|status)$")]
QuestionSetSortQuery = Annotated[str, Query(pattern="^(created_at|title)$")]
CurrentPrincipalDependency = Depends(get_current_principal)


@router.get(
    "/questions/topics",
    response_model=list[QuestionTopicRead],
    name="prepquestion:list_topics",
    dependencies=[Depends(require_permission("prepquestion.question.read"))],
)
async def list_topics(
    context: TenantContextDep,
    session: TenantSessionDep,
    search: SearchQuery = None,
    include_archived: bool = False,
) -> object:
    return await PrepQuestionService(session).list_topics(
        context,
        search=search,
        include_archived=include_archived,
    )


@router.post(
    "/questions/topics",
    response_model=QuestionTopicRead,
    status_code=status.HTTP_201_CREATED,
    name="prepquestion:create_topic",
    dependencies=[Depends(require_permission("prepquestion.question.manage"))],
)
async def create_topic(
    payload: QuestionTopicCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).create_topic(context, principal, payload)


@router.get(
    "/questions",
    response_model=QuestionPage,
    name="prepquestion:list_questions",
    dependencies=[Depends(require_permission("prepquestion.question.read"))],
)
async def list_questions(
    context: TenantContextDep,
    session: TenantSessionDep,
    limit: LimitQuery = 50,
    cursor: str | None = None,
    status_filter: Annotated[QuestionStatus | None, Query(alias="status")] = None,
    difficulty: QuestionDifficulty | None = None,
    question_type: QuestionType | None = None,
    topic_id: uuid.UUID | None = None,
    tag: Annotated[str | None, Query(max_length=80)] = None,
    search: SearchQuery = None,
    sort: QuestionSortQuery = "created_at",
) -> object:
    return await PrepQuestionService(session).list_questions(
        context,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        difficulty=difficulty,
        question_type=question_type,
        topic_id=topic_id,
        tag=tag,
        search=search,
        sort=sort,
    )


@router.post(
    "/questions",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
    name="prepquestion:create_question",
    dependencies=[Depends(require_permission("prepquestion.question.manage"))],
)
async def create_question(
    payload: QuestionCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).create_question(context, principal, payload)


@router.post(
    "/question-sets",
    response_model=QuestionSetRead,
    status_code=status.HTTP_201_CREATED,
    name="prepquestion:create_question_set",
    dependencies=[Depends(require_permission("prepquestion.question_set.manage"))],
)
async def create_question_set(
    payload: QuestionSetCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).create_question_set(context, principal, payload)


@router.get(
    "/question-sets",
    response_model=QuestionSetPage,
    name="prepquestion:list_question_sets",
    dependencies=[Depends(require_permission("prepquestion.question_set.manage"))],
)
async def list_question_sets(
    context: TenantContextDep,
    session: TenantSessionDep,
    limit: LimitQuery = 50,
    cursor: str | None = None,
    status_filter: Annotated[QuestionSetStatus | None, Query(alias="status")] = None,
    search: SearchQuery = None,
    sort: QuestionSetSortQuery = "created_at",
) -> object:
    return await PrepQuestionService(session).list_question_sets(
        context,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        search=search,
        sort=sort,
    )


@router.get(
    "/question-sets/{question_set_id}",
    response_model=QuestionSetDetailRead,
    name="prepquestion:get_question_set",
    dependencies=[Depends(require_permission("prepquestion.question_set.manage"))],
)
async def get_question_set(
    question_set_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepQuestionService(session).get_question_set(context, question_set_id)


@router.post(
    "/question-sets/{question_set_id}/items",
    response_model=QuestionSetDetailRead,
    status_code=status.HTTP_201_CREATED,
    name="prepquestion:add_question_set_item",
    dependencies=[Depends(require_permission("prepquestion.question_set.manage"))],
)
async def add_question_set_item(
    question_set_id: uuid.UUID,
    payload: QuestionSetItemCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).add_question_set_item(
        context,
        principal,
        question_set_id,
        payload,
    )


@router.patch(
    "/question-sets/{question_set_id}/reorder",
    response_model=QuestionSetDetailRead,
    name="prepquestion:reorder_question_set",
    dependencies=[Depends(require_permission("prepquestion.question_set.manage"))],
)
async def reorder_question_set(
    question_set_id: uuid.UUID,
    payload: QuestionSetReorderRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).reorder_question_set(
        context,
        principal,
        question_set_id,
        payload,
    )


@router.delete(
    "/question-sets/{question_set_id}/items/{item_id}",
    response_model=QuestionSetDetailRead,
    name="prepquestion:remove_question_set_item",
    dependencies=[Depends(require_permission("prepquestion.question_set.manage"))],
)
async def remove_question_set_item(
    question_set_id: uuid.UUID,
    item_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).remove_question_set_item(
        context,
        principal,
        question_set_id,
        item_id,
    )


@router.post(
    "/questions/ai-generation-jobs",
    response_model=AIQuestionGenerationJobRead,
    status_code=status.HTTP_201_CREATED,
    name="prepquestion:create_ai_generation_job",
    dependencies=[Depends(require_permission("prepquestion.ai_generation.manage"))],
)
async def create_ai_generation_job(
    payload: AIQuestionGenerationJobCreate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).create_ai_generation_job(context, principal, payload)


@router.get(
    "/questions/ai-generation-jobs/{job_id}",
    response_model=AIQuestionGenerationJobRead,
    name="prepquestion:get_ai_generation_job",
    dependencies=[Depends(require_permission("prepquestion.ai_generation.manage"))],
)
async def get_ai_generation_job(
    job_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepQuestionService(session).get_ai_generation_job(context, job_id)


@router.post(
    "/questions/ai-generation-jobs/{job_id}/approve",
    response_model=AIQuestionGenerationApprovalRead,
    name="prepquestion:approve_ai_generation_job",
    dependencies=[Depends(require_permission("prepquestion.ai_generation.manage"))],
)
async def approve_ai_generation_job(
    job_id: uuid.UUID,
    payload: AIQuestionGenerationApproveRequest,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).approve_ai_generation_job(
        context,
        principal,
        job_id,
        payload,
    )


@router.get(
    "/questions/{question_id}",
    response_model=QuestionRead,
    name="prepquestion:get_question",
    dependencies=[Depends(require_permission("prepquestion.question.read"))],
)
async def get_question(
    question_id: uuid.UUID,
    context: TenantContextDep,
    session: TenantSessionDep,
) -> object:
    return await PrepQuestionService(session).get_question(context, question_id)


@router.patch(
    "/questions/{question_id}",
    response_model=QuestionRead,
    name="prepquestion:update_question",
    dependencies=[Depends(require_permission("prepquestion.question.manage"))],
)
async def update_question(
    question_id: uuid.UUID,
    payload: QuestionUpdate,
    context: TenantContextDep,
    session: TenantSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    return await PrepQuestionService(session).update_question(
        context,
        principal,
        question_id,
        payload,
    )
