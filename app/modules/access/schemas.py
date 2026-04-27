from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.modules.access.enums import UserStatus, UserType
from app.shared.schemas import Schema


def normalize_email(value: str) -> str:
    return value.strip().lower()


class UserProfileRead(Schema):
    first_name: str | None
    last_name: str | None
    display_name: str | None
    avatar_url: str | None


class UserRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    email: EmailStr
    phone: str | None
    status: UserStatus
    user_type: UserType
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    profile: UserProfileRead | None = None


class RegisterInstitutionAdminRequest(Schema):
    tenant_id: uuid.UUID
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class LoginRequest(Schema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    tenant_id: uuid.UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class TokenPair(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_at: datetime


class AuthResponse(Schema):
    user: UserRead
    tokens: TokenPair


class RefreshRequest(Schema):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(Schema):
    refresh_token: str | None = Field(default=None, min_length=20)
    all_sessions: bool = False


class PasswordResetRequest(Schema):
    email: EmailStr
    tenant_id: uuid.UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetRequestResponse(Schema):
    status: str = "accepted"
    reset_token: str | None = None


class PasswordResetConfirmRequest(Schema):
    token: str = Field(min_length=20)
    new_password: str = Field(min_length=10, max_length=256)


class InvitationCreateRequest(Schema):
    tenant_id: uuid.UUID
    email: EmailStr
    role_id: uuid.UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class InvitationRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    role_id: uuid.UUID | None
    status: str
    expires_at: datetime
    created_at: datetime
    invitation_token: str | None = None


class InvitationAcceptRequest(Schema):
    token: str = Field(min_length=20)
    password: str = Field(min_length=10, max_length=256)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)


class PermissionRead(Schema):
    id: uuid.UUID
    code: str
    app_code: str
    resource: str
    action: str
    description: str | None
    is_active: bool


class RoleCreateRequest(Schema):
    tenant_id: uuid.UUID | None = None
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,118}[a-z0-9]$")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class RoleRead(Schema):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    code: str
    name: str
    description: str | None
    is_system: bool
    is_default: bool
    permissions: list[PermissionRead] = Field(default_factory=list)


class AssignRoleRequest(Schema):
    tenant_id: uuid.UUID | None = None
    role_id: uuid.UUID


class PermissionMatrixResponse(Schema):
    permissions: list[PermissionRead]
    roles: list[RoleRead]


class CurrentPermissionsResponse(Schema):
    permissions: list[str]
