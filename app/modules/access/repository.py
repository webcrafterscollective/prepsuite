from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.access.enums import RefreshTokenStatus
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
from app.shared.repository import Repository


def tenant_filter(
    column: Any,
    tenant_id: uuid.UUID | None,
) -> ColumnElement[bool]:
    if tenant_id is None:
        return cast(ColumnElement[bool], column.is_(None))
    return cast(ColumnElement[bool], column == tenant_id)


class UserRepository(Repository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_with_profile(self, user_id: uuid.UUID) -> User | None:
        statement = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.profile))
        )
        return cast(User | None, await self.session.scalar(statement))

    async def get_by_email(self, email: str, tenant_id: uuid.UUID | None) -> User | None:
        statement = (
            select(User)
            .where(
                User.email == email,
                tenant_filter(User.tenant_id, tenant_id),
                User.deleted_at.is_(None),
            )
            .options(selectinload(User.profile))
        )
        return cast(User | None, await self.session.scalar(statement))

    async def list_by_email(self, email: str) -> Sequence[User]:
        statement = (
            select(User)
            .where(User.email == email, User.deleted_at.is_(None))
            .options(selectinload(User.profile))
        )
        return (await self.session.scalars(statement)).all()


class UserProfileRepository(Repository[UserProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserProfile)


class PermissionRepository(Repository[Permission]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Permission)

    async def get_by_code(self, code: str) -> Permission | None:
        statement = select(Permission).where(Permission.code == code)
        return cast(Permission | None, await self.session.scalar(statement))

    async def list_all(self) -> Sequence[Permission]:
        statement = select(Permission).order_by(
            Permission.app_code,
            Permission.resource,
            Permission.action,
        )
        return (await self.session.scalars(statement)).all()

    async def list_by_codes(self, codes: Sequence[str]) -> Sequence[Permission]:
        if not codes:
            return []
        statement = select(Permission).where(Permission.code.in_(codes))
        return (await self.session.scalars(statement)).all()


class RoleRepository(Repository[Role]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Role)

    async def get_by_code(self, code: str, tenant_id: uuid.UUID | None) -> Role | None:
        statement = (
            select(Role)
            .where(
                Role.code == code,
                tenant_filter(Role.tenant_id, tenant_id),
                Role.deleted_at.is_(None),
            )
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        )
        return cast(Role | None, await self.session.scalar(statement))

    async def get_with_permissions(self, role_id: uuid.UUID) -> Role | None:
        statement = (
            select(Role)
            .where(Role.id == role_id, Role.deleted_at.is_(None))
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        )
        return cast(Role | None, await self.session.scalar(statement))

    async def list_for_tenant(self, tenant_id: uuid.UUID | None) -> Sequence[Role]:
        statement = (
            select(Role)
            .where(
                Role.deleted_at.is_(None),
                (Role.tenant_id == tenant_id) | Role.tenant_id.is_(None),
            )
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .order_by(Role.tenant_id.nulls_first(), Role.code)
        )
        return (await self.session.scalars(statement)).all()


class RolePermissionRepository(Repository[RolePermission]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RolePermission)


class UserRoleRepository(Repository[UserRole]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserRole)

    async def get_assignment(
        self,
        *,
        tenant_id: uuid.UUID | None,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> UserRole | None:
        statement = select(UserRole).where(
            tenant_filter(UserRole.tenant_id, tenant_id),
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
        return cast(UserRole | None, await self.session.scalar(statement))

    async def list_permission_codes(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
    ) -> set[str]:
        statement = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                tenant_filter(UserRole.tenant_id, tenant_id),
                Role.deleted_at.is_(None),
                Permission.is_active.is_(True),
            )
        )
        return set((await self.session.scalars(statement)).all())


class RefreshTokenRepository(Repository[RefreshToken]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RefreshToken)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        statement = (
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .options(selectinload(RefreshToken.user).selectinload(User.profile))
        )
        return cast(RefreshToken | None, await self.session.scalar(statement))

    async def revoke_family(self, family_id: uuid.UUID, status: RefreshTokenStatus) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .values(status=status.value, revoked_at=datetime.now(UTC))
        )

    async def revoke_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.status == RefreshTokenStatus.ACTIVE.value,
            )
            .values(status=RefreshTokenStatus.REVOKED.value, revoked_at=datetime.now(UTC))
        )


class LoginSessionRepository(Repository[LoginSession]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LoginSession)


class LoginHistoryRepository(Repository[LoginHistory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LoginHistory)


class PasswordResetTokenRepository(Repository[PasswordResetToken]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PasswordResetToken)

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        statement = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        return cast(PasswordResetToken | None, await self.session.scalar(statement))


class InvitationTokenRepository(Repository[InvitationToken]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InvitationToken)

    async def get_by_hash(self, token_hash: str) -> InvitationToken | None:
        statement = select(InvitationToken).where(InvitationToken.token_hash == token_hash)
        return cast(InvitationToken | None, await self.session.scalar(statement))
