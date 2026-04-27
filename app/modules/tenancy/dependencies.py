from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import PrepSuiteError
from app.core.security import decode_access_token, get_bearer_token
from app.core.tenant_context import (
    TenantContext,
    require_resolved_tenant,
    set_current_tenant_in_session,
    set_current_user_in_session,
)
from app.modules.tenancy.service import TenantResolutionHints, TenantService

IGNORED_SUBDOMAINS = {"api", "app", "admin", "www", "localhost"}
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def parse_uuid_header(value: str | None, header_name: str) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise PrepSuiteError(
            "invalid_header",
            f"{header_name} must be a valid UUID.",
            status_code=400,
        ) from exc


def get_request_host(request: Request) -> str | None:
    host = request.headers.get("host")
    if not host:
        return None
    return host.split(":", maxsplit=1)[0].lower()


def extract_subdomain(host: str | None) -> str | None:
    if host is None:
        return None
    parts = host.split(".")
    if len(parts) < 3:
        return None
    candidate = parts[0].lower()
    if candidate in IGNORED_SUBDOMAINS:
        return None
    return candidate


async def get_tenant_context(
    request: Request,
    session: DbSessionDep,
) -> TenantContext:
    host = get_request_host(request)
    token = get_bearer_token(request.headers.get("Authorization"))
    token_payload = decode_access_token(token) if token else {}
    token_tenant_id = token_payload.get("tid")
    token_user_id = token_payload.get("sub")
    tenant_id = parse_uuid_header(request.headers.get("X-Tenant-ID"), "X-Tenant-ID")
    user_id = parse_uuid_header(request.headers.get("X-User-ID"), "X-User-ID")
    if tenant_id is None and isinstance(token_tenant_id, str):
        tenant_id = parse_uuid_header(token_tenant_id, "token.tid")
    if user_id is None and isinstance(token_user_id, str):
        user_id = parse_uuid_header(token_user_id, "token.sub")
    if user_id is not None:
        await set_current_user_in_session(session, user_id)
    slug = request.headers.get("X-Tenant-Slug")
    domain = request.headers.get("X-Tenant-Domain") or host
    hints = TenantResolutionHints(
        tenant_id=tenant_id,
        slug=slug.lower() if slug else None,
        domain=domain.lower() if domain else None,
        subdomain=extract_subdomain(host),
        user_id=user_id,
    )
    context = await TenantService(session).resolve_tenant(hints)
    request.state.tenant_context = context
    return context


async def require_tenant_context(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    return require_resolved_tenant(context)


async def get_tenant_scoped_session(
    session: DbSessionDep,
    context: Annotated[TenantContext, Depends(require_tenant_context)],
) -> AsyncIterator[AsyncSession]:
    tenant_id = context.tenant_id
    if tenant_id is None:
        raise AssertionError("Tenant context dependency returned an unresolved tenant.")
    await set_current_tenant_in_session(session, tenant_id)
    yield session
