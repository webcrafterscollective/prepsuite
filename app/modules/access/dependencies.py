from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.security import decode_access_token
from app.core.tenant_context import set_current_tenant_in_session, set_current_user_in_session
from app.modules.access.enums import UserStatus
from app.modules.access.models import User
from app.modules.access.repository import UserRepository
from app.modules.access.service import AccessService, RequestMetadata

bearer_scheme = HTTPBearer(auto_error=False)
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
BearerCredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def get_request_metadata(request: Request) -> RequestMetadata:
    client_ip = request.client.host if request.client else None
    forwarded_for = request.headers.get("X-Forwarded-For")
    ip_address = forwarded_for.split(",")[0] if forwarded_for else client_ip
    return RequestMetadata(
        ip_address=ip_address,
        user_agent=request.headers.get("User-Agent"),
    )


async def get_current_user(
    credentials: BearerCredentialsDep,
    session: DbSessionDep,
) -> User:
    if credentials is None:
        raise PrepSuiteError(
            "authentication_required",
            "Authentication is required.",
            status_code=401,
        )
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    tenant_id = payload.get("tid")
    if not isinstance(user_id, str):
        raise PrepSuiteError(
            "invalid_token",
            "Access token subject is missing.",
            status_code=401,
        )

    from uuid import UUID

    parsed_user_id = UUID(user_id)
    await set_current_user_in_session(session, parsed_user_id)
    parsed_tenant_id = UUID(tenant_id) if isinstance(tenant_id, str) else None
    if parsed_tenant_id is not None:
        await set_current_tenant_in_session(session, parsed_tenant_id)
    user = await UserRepository(session).get_with_profile(parsed_user_id)
    if user is None or user.deleted_at is not None:
        raise PrepSuiteError(
            "user_not_found",
            "Authenticated user was not found.",
            status_code=401,
        )
    if user.status != UserStatus.ACTIVE.value:
        raise PrepSuiteError("user_not_active", "User account is not active.", status_code=403)
    if user.tenant_id != parsed_tenant_id:
        raise PrepSuiteError("tenant_access_denied", "Token tenant mismatch.", status_code=403)
    return user


async def get_current_principal(
    user: Annotated[User, Depends(get_current_user)],
    session: DbSessionDep,
) -> Principal:
    if user.tenant_id is not None:
        await set_current_tenant_in_session(session, user.tenant_id)
    permissions = await AccessService(session).current_permissions(
        Principal(user_id=user.id, tenant_id=user.tenant_id)
    )
    return Principal(user_id=user.id, tenant_id=user.tenant_id, permissions=frozenset(permissions))
