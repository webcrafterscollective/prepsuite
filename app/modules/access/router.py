from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.permissions import Principal, require_permission
from app.core.tenant_context import TenantContext
from app.modules.access.dependencies import (
    get_current_principal,
    get_current_user,
    get_request_metadata,
)
from app.modules.access.models import Role, User
from app.modules.access.schemas import (
    AssignRoleRequest,
    AuthResponse,
    CurrentPermissionsResponse,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationRead,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    PermissionMatrixResponse,
    RefreshRequest,
    RegisterInstitutionAdminRequest,
    RoleCreateRequest,
    RoleRead,
    TokenPair,
    UserRead,
)
from app.modules.access.service import AccessService, IssuedTokenPair
from app.modules.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/access", tags=["PrepAccess"])
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
TenantContextDep = Annotated[TenantContext, Depends(get_tenant_context)]
CurrentUserDependency = Depends(get_current_user)
CurrentPrincipalDependency = Depends(get_current_principal)


def token_pair_response(tokens: IssuedTokenPair) -> TokenPair:
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        refresh_expires_at=tokens.refresh_expires_at,
    )


def role_response(role: Role) -> dict[str, object]:
    return {
        "id": role.id,
        "tenant_id": role.tenant_id,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "is_default": role.is_default,
        "permissions": [item.permission for item in role.permissions],
    }


@router.post(
    "/register-institution-admin",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    name="prepaccess:register_institution_admin",
)
async def register_institution_admin(
    payload: RegisterInstitutionAdminRequest,
    session: DbSessionDep,
) -> object:
    user, tokens = await AccessService(session).register_institution_admin(payload)
    return {"user": user, "tokens": token_pair_response(tokens)}


@router.post("/login", response_model=AuthResponse, name="prepaccess:login")
async def login(
    payload: LoginRequest,
    request: Request,
    session: DbSessionDep,
    tenant_context: TenantContextDep,
) -> object:
    user, tokens = await AccessService(session).login(
        payload,
        tenant_id=tenant_context.tenant_id,
        metadata=get_request_metadata(request),
    )
    return {"user": user, "tokens": token_pair_response(tokens)}


@router.post("/refresh", response_model=AuthResponse, name="prepaccess:refresh")
async def refresh_token(
    payload: RefreshRequest,
    request: Request,
    session: DbSessionDep,
) -> object:
    user, tokens = await AccessService(session).refresh(
        payload.refresh_token,
        metadata=get_request_metadata(request),
    )
    return {"user": user, "tokens": token_pair_response(tokens)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, name="prepaccess:logout")
async def logout(
    payload: LogoutRequest,
    response: Response,
    session: DbSessionDep,
    user: User = CurrentUserDependency,
) -> Response:
    await AccessService(session).logout(
        user_id=user.id,
        refresh_token=payload.refresh_token,
        all_sessions=payload.all_sessions,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    name="prepaccess:request_password_reset",
)
async def request_password_reset(
    payload: PasswordResetRequest,
    session: DbSessionDep,
) -> object:
    reset_token = await AccessService(session).request_password_reset(payload)
    return PasswordResetRequestResponse(reset_token=reset_token)


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    name="prepaccess:confirm_password_reset",
)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    response: Response,
    session: DbSessionDep,
) -> Response:
    await AccessService(session).confirm_password_reset(payload)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("prepaccess.user.invite"))],
    name="prepaccess:invite_user",
)
async def invite_user(
    payload: InvitationCreateRequest,
    session: DbSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    invitation, raw_token = await AccessService(session).invite_user(
        payload,
        actor_user_id=principal.user_id,
    )
    return {**InvitationRead.model_validate(invitation).model_dump(), "invitation_token": raw_token}


@router.post(
    "/invitations/accept",
    response_model=AuthResponse,
    name="prepaccess:accept_invitation",
)
async def accept_invitation(
    payload: InvitationAcceptRequest,
    session: DbSessionDep,
) -> object:
    user, tokens = await AccessService(session).accept_invitation(payload)
    return {"user": user, "tokens": token_pair_response(tokens)}


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("prepaccess.role.manage"))],
    name="prepaccess:create_custom_role",
)
async def create_custom_role(
    payload: RoleCreateRequest,
    session: DbSessionDep,
) -> object:
    role = await AccessService(session).create_custom_role(payload)
    return role_response(role)


@router.post(
    "/users/{user_id}/roles",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("prepaccess.role.manage"))],
    name="prepaccess:assign_role",
)
async def assign_role(
    user_id: uuid.UUID,
    payload: AssignRoleRequest,
    response: Response,
    session: DbSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> Response:
    await AccessService(session).assign_role_to_user(
        user_id=user_id,
        payload=payload,
        actor_user_id=principal.user_id,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("prepaccess.role.manage"))],
    name="prepaccess:remove_role",
)
async def remove_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    response: Response,
    session: DbSessionDep,
    tenant_context: TenantContextDep,
) -> Response:
    await AccessService(session).remove_role_from_user(
        user_id=user_id,
        role_id=role_id,
        tenant_id=tenant_context.tenant_id,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get(
    "/permission-matrix",
    response_model=PermissionMatrixResponse,
    dependencies=[Depends(require_permission("prepaccess.permission.read"))],
    name="prepaccess:permission_matrix",
)
async def permission_matrix(
    session: DbSessionDep,
    principal: Principal = CurrentPrincipalDependency,
) -> object:
    permissions, roles = await AccessService(session).permission_matrix(principal.tenant_id)
    return {
        "permissions": permissions,
        "roles": [role_response(role) for role in roles],
    }


@router.get("/me", response_model=UserRead, name="prepaccess:current_user")
async def current_user(user: User = CurrentUserDependency) -> object:
    return user


@router.get(
    "/me/permissions",
    response_model=CurrentPermissionsResponse,
    name="prepaccess:current_permissions",
)
async def current_permissions(principal: Principal = CurrentPrincipalDependency) -> object:
    return {"permissions": sorted(principal.permissions)}
