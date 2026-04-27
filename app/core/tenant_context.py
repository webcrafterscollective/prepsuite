from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PrepSuiteError

TenantSource = Literal["unresolved", "header", "subdomain", "authenticated_user"]


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID | None
    source: TenantSource = "unresolved"
    slug: str | None = None
    domain: str | None = None
    user_id: UUID | None = None


async def set_current_tenant_in_session(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def set_current_user_in_session(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def require_resolved_tenant(context: TenantContext) -> TenantContext:
    if context.tenant_id is None:
        raise PrepSuiteError(
            "tenant_required",
            "A tenant context is required for this operation.",
            status_code=400,
        )
    return context


def ensure_tenant_access(entity_tenant_id: UUID, context: TenantContext) -> None:
    resolved_context = require_resolved_tenant(context)
    if entity_tenant_id != resolved_context.tenant_id:
        raise PrepSuiteError(
            "tenant_access_denied",
            "The requested resource does not belong to the current tenant.",
            status_code=403,
        )
