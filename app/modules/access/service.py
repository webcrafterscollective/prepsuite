from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import PrepSuiteError
from app.core.permissions import Principal
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_secret,
    verify_password,
)
from app.core.tenant_context import set_current_tenant_in_session, set_current_user_in_session
from app.modules.access.enums import (
    InvitationStatus,
    LoginSessionStatus,
    RefreshTokenStatus,
    UserStatus,
    UserType,
)
from app.modules.access.models import (
    InvitationToken,
    LoginHistory,
    LoginSession,
    PasswordResetToken,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserProfile,
    UserRole,
)
from app.modules.access.permissions_catalog import DEFAULT_PERMISSIONS
from app.modules.access.repository import (
    InvitationTokenRepository,
    LoginHistoryRepository,
    LoginSessionRepository,
    PasswordResetTokenRepository,
    PermissionRepository,
    RefreshTokenRepository,
    RolePermissionRepository,
    RoleRepository,
    UserProfileRepository,
    UserRepository,
    UserRoleRepository,
)
from app.modules.access.schemas import (
    AssignRoleRequest,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterInstitutionAdminRequest,
    RoleCreateRequest,
)
from app.modules.tenancy.models import TenantUser
from app.modules.tenancy.service import TenantService


@dataclass(frozen=True)
class RequestMetadata:
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class IssuedTokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_at: datetime


class InMemoryLoginRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, deque[datetime]] = defaultdict(deque)

    def assert_allowed(self, key: str, settings: Settings) -> None:
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=settings.login_rate_limit_window_seconds)
        attempts = self._attempts[key]
        while attempts and attempts[0] < window_start:
            attempts.popleft()
        if len(attempts) >= settings.login_rate_limit_attempts:
            raise PrepSuiteError(
                "login_rate_limited",
                "Too many failed login attempts. Please try again later.",
                status_code=429,
            )

    def record_failure(self, key: str) -> None:
        self._attempts[key].append(datetime.now(UTC))

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


login_rate_limiter = InMemoryLoginRateLimiter()


class AccessService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.users = UserRepository(session)
        self.profiles = UserProfileRepository(session)
        self.permissions = PermissionRepository(session)
        self.roles = RoleRepository(session)
        self.role_permissions = RolePermissionRepository(session)
        self.user_roles = UserRoleRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.login_sessions = LoginSessionRepository(session)
        self.login_history = LoginHistoryRepository(session)
        self.password_resets = PasswordResetTokenRepository(session)
        self.invitations = InvitationTokenRepository(session)

    async def register_institution_admin(
        self,
        payload: RegisterInstitutionAdminRequest,
    ) -> tuple[User, IssuedTokenPair]:
        await TenantService(self.session).get_tenant(payload.tenant_id)
        await set_current_tenant_in_session(self.session, payload.tenant_id)
        await self.ensure_default_permissions()
        admin_role = await self.ensure_system_role(
            tenant_id=payload.tenant_id,
            code="institution_admin",
            name="Institution Admin",
            permission_codes=[item["code"] for item in DEFAULT_PERMISSIONS],
            is_default=True,
        )
        user = User(
            tenant_id=payload.tenant_id,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            status=UserStatus.ACTIVE.value,
            user_type=UserType.INSTITUTION_ADMIN.value,
        )
        profile = UserProfile(
            tenant_id=payload.tenant_id,
            user=user,
            first_name=payload.first_name,
            last_name=payload.last_name,
            display_name=self._display_name(payload.first_name, payload.last_name),
        )
        self.session.add_all([user, profile])
        try:
            await self.session.flush()
            self.session.add(
                TenantUser(
                    tenant_id=payload.tenant_id,
                    user_id=user.id,
                    status="active",
                    is_primary_admin=True,
                )
            )
            await self.assign_role_to_user(
                user_id=user.id,
                payload=AssignRoleRequest(tenant_id=payload.tenant_id, role_id=admin_role.id),
                actor_user_id=user.id,
                commit=False,
            )
            tokens = await self._issue_token_pair(user)
            await self._refresh_user_for_response(user)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError(
                "user_conflict",
                "A user with this email already exists for the tenant.",
                status_code=409,
            ) from exc
        return user, tokens

    async def login(
        self,
        payload: LoginRequest,
        *,
        tenant_id: uuid.UUID | None,
        metadata: RequestMetadata,
    ) -> tuple[User, IssuedTokenPair]:
        resolved_tenant_id = payload.tenant_id or tenant_id
        if resolved_tenant_id is not None:
            await set_current_tenant_in_session(self.session, resolved_tenant_id)

        key = f"{payload.email}:{metadata.ip_address or 'unknown'}"
        login_rate_limiter.assert_allowed(key, self.settings)
        user = await self._find_login_user(payload.email, resolved_tenant_id)
        if user is None or not verify_password(payload.password, user.password_hash):
            login_rate_limiter.record_failure(key)
            await self._record_login_history(
                email=payload.email,
                tenant_id=resolved_tenant_id,
                user_id=user.id if user else None,
                success=False,
                failure_reason="invalid_credentials",
                metadata=metadata,
            )
            await self.session.commit()
            raise PrepSuiteError(
                "invalid_credentials",
                "Invalid email or password.",
                status_code=401,
            )

        if user.status != UserStatus.ACTIVE.value:
            login_rate_limiter.record_failure(key)
            await self._record_login_history(
                email=payload.email,
                tenant_id=user.tenant_id,
                user_id=user.id,
                success=False,
                failure_reason=f"user_{user.status}",
                metadata=metadata,
            )
            await self.session.commit()
            raise PrepSuiteError("user_not_active", "User account is not active.", status_code=403)

        await set_current_user_in_session(self.session, user.id)
        if user.tenant_id is not None:
            await set_current_tenant_in_session(self.session, user.tenant_id)
        user.last_login_at = datetime.now(UTC)
        tokens = await self._issue_token_pair(user, metadata=metadata)
        await self._record_login_history(
            email=payload.email,
            tenant_id=user.tenant_id,
            user_id=user.id,
            success=True,
            failure_reason=None,
            metadata=metadata,
        )
        await self._refresh_user_for_response(user)
        await self.session.commit()
        login_rate_limiter.reset(key)
        return user, tokens

    async def refresh(
        self,
        payload: str,
        metadata: RequestMetadata,
    ) -> tuple[User, IssuedTokenPair]:
        tenant_id, user_id = await self._apply_scope_from_token(payload)
        if user_id is None:
            raise PrepSuiteError(
                "invalid_refresh_token",
                "Refresh token is invalid.",
                status_code=401,
            )
        token_hash = hash_secret(payload)
        refresh_token = await self.refresh_tokens.get_by_hash(token_hash)
        if refresh_token is None:
            raise PrepSuiteError(
                "invalid_refresh_token",
                "Refresh token is invalid.",
                status_code=401,
            )

        if refresh_token.user_id != user_id or refresh_token.tenant_id != tenant_id:
            raise PrepSuiteError(
                "invalid_refresh_token",
                "Refresh token is invalid.",
                status_code=401,
            )

        if refresh_token.status != RefreshTokenStatus.ACTIVE.value:
            await self.refresh_tokens.revoke_family(
                refresh_token.family_id,
                RefreshTokenStatus.REUSED,
            )
            await self.session.commit()
            raise PrepSuiteError(
                "refresh_token_reuse_detected",
                "Refresh token reuse was detected and the token family was revoked.",
                status_code=401,
            )
        if refresh_token.expires_at <= datetime.now(UTC):
            refresh_token.status = RefreshTokenStatus.REVOKED.value
            refresh_token.revoked_at = datetime.now(UTC)
            await self.session.commit()
            raise PrepSuiteError("refresh_token_expired", "Refresh token expired.", status_code=401)

        user = refresh_token.user
        if user.status != UserStatus.ACTIVE.value:
            raise PrepSuiteError("user_not_active", "User account is not active.", status_code=403)

        refresh_token.status = RefreshTokenStatus.ROTATED.value
        refresh_token.revoked_at = datetime.now(UTC)
        tokens = await self._issue_token_pair(
            user,
            metadata=metadata,
            family_id=refresh_token.family_id,
            parent_token_id=refresh_token.id,
        )
        await self.session.commit()
        return user, tokens

    async def logout(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token: str | None,
        all_sessions: bool,
    ) -> None:
        await set_current_user_in_session(self.session, user_id)
        if all_sessions:
            await self.refresh_tokens.revoke_for_user(user_id)
            await self.session.commit()
            return
        if refresh_token is None:
            raise PrepSuiteError(
                "refresh_token_required",
                "Refresh token is required.",
                status_code=400,
            )
        await self._apply_scope_from_token(refresh_token)
        stored = await self.refresh_tokens.get_by_hash(hash_secret(refresh_token))
        if stored is None or stored.user_id != user_id:
            raise PrepSuiteError(
                "invalid_refresh_token",
                "Refresh token is invalid.",
                status_code=401,
            )
        stored.status = RefreshTokenStatus.REVOKED.value
        stored.revoked_at = datetime.now(UTC)
        await self.session.commit()

    async def request_password_reset(self, payload: PasswordResetRequest) -> str | None:
        if payload.tenant_id is not None:
            await set_current_tenant_in_session(self.session, payload.tenant_id)
        user = await self._find_login_user(payload.email, payload.tenant_id)
        if user is None:
            return None
        raw_token = self._build_scoped_token(user.tenant_id, user.id)
        reset = PasswordResetToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=hash_secret(raw_token),
            expires_at=datetime.now(UTC)
            + timedelta(minutes=self.settings.password_reset_token_ttl_minutes),
        )
        await self.password_resets.add(reset)
        await self.session.commit()
        return raw_token

    async def confirm_password_reset(self, payload: PasswordResetConfirmRequest) -> None:
        await self._apply_scope_from_token(payload.token)
        reset = await self.password_resets.get_by_hash(hash_secret(payload.token))
        if reset is None or reset.used_at is not None or reset.expires_at <= datetime.now(UTC):
            raise PrepSuiteError(
                "invalid_reset_token",
                "Password reset token is invalid.",
                status_code=401,
            )
        await set_current_user_in_session(self.session, reset.user_id)
        if reset.tenant_id is not None:
            await set_current_tenant_in_session(self.session, reset.tenant_id)
        user = await self.users.get_with_profile(reset.user_id)
        if user is None:
            raise PrepSuiteError("user_not_found", "User was not found.", status_code=404)
        user.password_hash = hash_password(payload.new_password)
        reset.used_at = datetime.now(UTC)
        await self.refresh_tokens.revoke_for_user(user.id)
        await self.session.commit()

    async def invite_user(
        self,
        payload: InvitationCreateRequest,
        *,
        actor_user_id: uuid.UUID | None,
    ) -> tuple[InvitationToken, str]:
        await TenantService(self.session).get_tenant(payload.tenant_id)
        await set_current_tenant_in_session(self.session, payload.tenant_id)
        if payload.role_id is not None:
            role = await self.roles.get_with_permissions(payload.role_id)
            if role is None or role.tenant_id != payload.tenant_id:
                raise PrepSuiteError("role_not_found", "Role was not found.", status_code=404)
        raw_token = self._build_scoped_token(payload.tenant_id, None)
        invitation = InvitationToken(
            tenant_id=payload.tenant_id,
            email=payload.email,
            role_id=payload.role_id,
            token_hash=hash_secret(raw_token),
            invited_by=actor_user_id,
            expires_at=datetime.now(UTC) + timedelta(days=self.settings.invitation_token_ttl_days),
        )
        await self.invitations.add(invitation)
        await self.session.flush()
        await self.session.refresh(invitation)
        await self.session.commit()
        return invitation, raw_token

    async def accept_invitation(
        self,
        payload: InvitationAcceptRequest,
    ) -> tuple[User, IssuedTokenPair]:
        await self._apply_scope_from_token(payload.token)
        invitation = await self.invitations.get_by_hash(hash_secret(payload.token))
        if invitation is None:
            raise PrepSuiteError(
                "invalid_invitation",
                "Invitation token is invalid.",
                status_code=401,
            )
        await set_current_tenant_in_session(self.session, invitation.tenant_id)
        invitation_expired = invitation.expires_at <= datetime.now(UTC)
        if invitation.status != InvitationStatus.PENDING.value or invitation_expired:
            raise PrepSuiteError(
                "invalid_invitation",
                "Invitation token is invalid or expired.",
                status_code=401,
            )

        user = User(
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            password_hash=hash_password(payload.password),
            status=UserStatus.ACTIVE.value,
            user_type=UserType.EMPLOYEE.value,
        )
        profile = UserProfile(
            tenant_id=invitation.tenant_id,
            user=user,
            first_name=payload.first_name,
            last_name=payload.last_name,
            display_name=self._display_name(payload.first_name, payload.last_name),
        )
        self.session.add_all([user, profile])
        try:
            await self.session.flush()
            self.session.add(TenantUser(tenant_id=invitation.tenant_id, user_id=user.id))
            if invitation.role_id is not None:
                await self.assign_role_to_user(
                    user_id=user.id,
                    payload=AssignRoleRequest(
                        tenant_id=invitation.tenant_id,
                        role_id=invitation.role_id,
                    ),
                    actor_user_id=invitation.invited_by,
                    commit=False,
                )
            invitation.accepted_user_id = user.id
            invitation.accepted_at = datetime.now(UTC)
            invitation.status = InvitationStatus.ACCEPTED.value
            tokens = await self._issue_token_pair(user)
            await self._refresh_user_for_response(user)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PrepSuiteError("user_conflict", "User already exists.", status_code=409) from exc
        return user, tokens

    async def create_custom_role(self, payload: RoleCreateRequest) -> Role:
        if payload.tenant_id is not None:
            await set_current_tenant_in_session(self.session, payload.tenant_id)
        await self.ensure_default_permissions()
        existing = await self.roles.get_by_code(payload.code, payload.tenant_id)
        if existing is not None:
            raise PrepSuiteError("role_conflict", "Role code already exists.", status_code=409)
        role = Role(
            tenant_id=payload.tenant_id,
            code=payload.code,
            name=payload.name,
            description=payload.description,
            is_system=False,
            is_default=False,
        )
        await self.roles.add(role)
        await self._replace_role_permissions(role, payload.permission_codes)
        await self.session.refresh(role, attribute_names=["permissions"])
        await self.session.commit()
        return role

    async def assign_role_to_user(
        self,
        *,
        user_id: uuid.UUID,
        payload: AssignRoleRequest,
        actor_user_id: uuid.UUID | None,
        commit: bool = True,
    ) -> UserRole:
        if payload.tenant_id is not None:
            await set_current_tenant_in_session(self.session, payload.tenant_id)
        user = await self.users.get_with_profile(user_id)
        role = await self.roles.get_with_permissions(payload.role_id)
        if user is None:
            raise PrepSuiteError("user_not_found", "User was not found.", status_code=404)
        if role is None:
            raise PrepSuiteError("role_not_found", "Role was not found.", status_code=404)
        if user.tenant_id != payload.tenant_id or role.tenant_id != payload.tenant_id:
            raise PrepSuiteError(
                "tenant_access_denied",
                "Role assignment tenant mismatch.",
                status_code=403,
            )
        existing = await self.user_roles.get_assignment(
            tenant_id=payload.tenant_id,
            user_id=user_id,
            role_id=payload.role_id,
        )
        if existing is not None:
            return existing
        assignment = UserRole(
            tenant_id=payload.tenant_id,
            user_id=user_id,
            role_id=payload.role_id,
            assigned_by=actor_user_id,
        )
        await self.user_roles.add(assignment)
        if commit:
            await self.session.commit()
        return assignment

    async def remove_role_from_user(
        self,
        *,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
    ) -> None:
        if tenant_id is not None:
            await set_current_tenant_in_session(self.session, tenant_id)
        assignment = await self.user_roles.get_assignment(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role_id,
        )
        if assignment is None:
            raise PrepSuiteError(
                "role_assignment_not_found",
                "Role assignment was not found.",
                status_code=404,
            )
        await self.session.delete(assignment)
        await self.session.commit()

    async def permission_matrix(
        self,
        tenant_id: uuid.UUID | None,
    ) -> tuple[list[Permission], list[Role]]:
        if tenant_id is not None:
            await set_current_tenant_in_session(self.session, tenant_id)
        await self.ensure_default_permissions()
        permissions = list(await self.permissions.list_all())
        roles = list(await self.roles.list_for_tenant(tenant_id))
        return permissions, roles

    async def current_permissions(self, principal: Principal) -> set[str]:
        if principal.tenant_id is not None:
            await set_current_tenant_in_session(self.session, principal.tenant_id)
        return await self.user_roles.list_permission_codes(principal.user_id, principal.tenant_id)

    async def ensure_default_permissions(self) -> None:
        for item in DEFAULT_PERMISSIONS:
            permission = await self.permissions.get_by_code(item["code"])
            if permission is None:
                await self.permissions.add(Permission(**item, is_active=True))
        await self.session.flush()

    async def ensure_system_role(
        self,
        *,
        tenant_id: uuid.UUID | None,
        code: str,
        name: str,
        permission_codes: list[str],
        is_default: bool,
    ) -> Role:
        if tenant_id is not None:
            await set_current_tenant_in_session(self.session, tenant_id)
        role = await self.roles.get_by_code(code, tenant_id)
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                code=code,
                name=name,
                is_system=True,
                is_default=is_default,
            )
            await self.roles.add(role)
        await self._replace_role_permissions(role, permission_codes)
        return role

    async def _replace_role_permissions(self, role: Role, permission_codes: list[str]) -> None:
        await self.session.flush()
        permissions = await self.permissions.list_by_codes(permission_codes)
        found_codes = {permission.code for permission in permissions}
        missing = sorted(set(permission_codes) - found_codes)
        if missing:
            raise PrepSuiteError(
                "permission_not_found",
                "One or more permissions were not found.",
                status_code=404,
                details={"missing": missing},
            )
        await self.session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        await self.session.flush()
        for permission in permissions:
            self.session.add(
                RolePermission(
                    tenant_id=role.tenant_id,
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )
        await self.session.flush()

    async def _issue_token_pair(
        self,
        user: User,
        *,
        metadata: RequestMetadata | None = None,
        family_id: uuid.UUID | None = None,
        parent_token_id: uuid.UUID | None = None,
    ) -> IssuedTokenPair:
        raw_refresh_token = self._build_scoped_token(user.tenant_id, user.id, size=48)
        refresh_expires_at = datetime.now(UTC) + timedelta(
            days=self.settings.refresh_token_ttl_days
        )
        access_token = create_access_token(
            subject=user.id,
            tenant_id=user.tenant_id,
            user_type=user.user_type,
            settings=self.settings,
        )
        refresh_token = RefreshToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=hash_secret(raw_refresh_token),
            family_id=family_id or uuid.uuid4(),
            parent_token_id=parent_token_id,
            expires_at=refresh_expires_at,
        )
        await self.refresh_tokens.add(refresh_token)
        await self.session.flush()
        if parent_token_id is not None:
            parent = await self.refresh_tokens.get(parent_token_id)
            if parent is not None:
                parent.replaced_by_token_id = refresh_token.id
        if metadata is not None:
            session = LoginSession(
                tenant_id=user.tenant_id,
                user_id=user.id,
                refresh_token_id=refresh_token.id,
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
                last_seen_at=datetime.now(UTC),
                status=LoginSessionStatus.ACTIVE.value,
            )
            await self.login_sessions.add(session)
        return IssuedTokenPair(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=self.settings.access_token_ttl_minutes * 60,
            refresh_expires_at=refresh_expires_at,
        )

    async def _find_login_user(self, email: str, tenant_id: uuid.UUID | None) -> User | None:
        if tenant_id is not None:
            return await self.users.get_by_email(email, tenant_id)
        candidates = list(await self.users.list_by_email(email))
        if len(candidates) > 1:
            raise PrepSuiteError(
                "tenant_required",
                "Tenant context is required for this login.",
                status_code=400,
            )
        return candidates[0] if candidates else None

    async def _record_login_history(
        self,
        *,
        email: str,
        tenant_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        success: bool,
        failure_reason: str | None,
        metadata: RequestMetadata,
    ) -> None:
        await self.login_history.add(
            LoginHistory(
                tenant_id=tenant_id,
                user_id=user_id,
                email=email,
                success=success,
                failure_reason=failure_reason,
                ip_address=metadata.ip_address,
                user_agent=metadata.user_agent,
            )
        )

    def _display_name(self, first_name: str, last_name: str | None) -> str:
        return " ".join(part for part in [first_name, last_name] if part).strip()

    async def _refresh_user_for_response(self, user: User) -> None:
        await self.session.flush()
        await self.session.refresh(user)
        await self.session.refresh(user, attribute_names=["profile"])

    def _build_scoped_token(
        self,
        tenant_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        *,
        size: int = 32,
    ) -> str:
        tenant_part = str(tenant_id) if tenant_id is not None else "platform"
        user_part = str(user_id) if user_id is not None else "public"
        return f"{tenant_part}.{user_part}.{generate_opaque_token(size)}"

    async def _apply_scope_from_token(
        self,
        token: str,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        try:
            tenant_part, user_part, _secret = token.split(".", maxsplit=2)
            tenant_id = None if tenant_part == "platform" else uuid.UUID(tenant_part)
            user_id = None if user_part == "public" else uuid.UUID(user_part)
        except (ValueError, AttributeError) as exc:
            raise PrepSuiteError(
                "invalid_token",
                "Token is invalid.",
                status_code=401,
            ) from exc
        if user_id is not None:
            await set_current_user_in_session(self.session, user_id)
        if tenant_id is not None:
            await set_current_tenant_in_session(self.session, tenant_id)
        return tenant_id, user_id
