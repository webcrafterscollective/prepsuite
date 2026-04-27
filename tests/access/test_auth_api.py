from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import decode_access_token
from app.core.tenant_context import set_current_tenant_in_session
from app.modules.access.models import LoginHistory


async def create_tenant(client: AsyncClient, slug: str) -> str:
    response = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "status": "active",
            "plan_type": "starter",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def register_admin(
    client: AsyncClient,
    tenant_id: str,
    *,
    email: str = "admin@prepsuite.io",
    password: str = "correct-horse-battery",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/access/register-institution-admin",
        json={
            "tenant_id": tenant_id,
            "email": email,
            "password": password,
            "first_name": "Ada",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_register_login_current_user_permissions_and_login_history(
    tenancy_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_id = await create_tenant(tenancy_client, "access-login")
    registered = await register_admin(tenancy_client, tenant_id)
    user = registered["user"]
    assert isinstance(user, dict)

    login = await tenancy_client.post(
        "/api/v1/access/login",
        headers={"X-Tenant-ID": tenant_id, "User-Agent": "pytest"},
        json={"email": "admin@prepsuite.io", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200, login.text
    access_token = login.json()["tokens"]["access_token"]
    claims = decode_access_token(access_token)
    assert claims["sub"] == user["id"]
    assert claims["tid"] == tenant_id
    assert claims["typ"] == "access"
    assert claims["user_type"] == "institution_admin"

    current_user = await tenancy_client.get("/api/v1/access/me", headers=bearer(access_token))
    assert current_user.status_code == 200, current_user.text
    assert current_user.json()["id"] == user["id"]

    permissions = await tenancy_client.get(
        "/api/v1/access/me/permissions",
        headers=bearer(access_token),
    )
    assert permissions.status_code == 200, permissions.text
    assert "prepaccess.role.manage" in permissions.json()["permissions"]

    matrix = await tenancy_client.get(
        "/api/v1/access/permission-matrix",
        headers=bearer(access_token),
    )
    assert matrix.status_code == 200, matrix.text
    assert any(item["code"] == "prepaccess.user.invite" for item in matrix.json()["permissions"])

    async with session_factory() as session:
        await set_current_tenant_in_session(session, uuid.UUID(tenant_id))
        history_count = await session.scalar(
            select(func.count(LoginHistory.id)).where(LoginHistory.success.is_(True))
        )
    assert history_count == 1


async def test_refresh_token_rotation_detects_reuse(tenancy_client: AsyncClient) -> None:
    tenant_id = await create_tenant(tenancy_client, "access-refresh")
    registered = await register_admin(
        tenancy_client,
        tenant_id,
        email="refresh@prepsuite.io",
    )
    tokens = registered["tokens"]
    assert isinstance(tokens, dict)
    original_refresh_token = tokens["refresh_token"]

    refreshed = await tenancy_client.post(
        "/api/v1/access/refresh",
        json={"refresh_token": original_refresh_token},
    )
    assert refreshed.status_code == 200, refreshed.text
    rotated_refresh_token = refreshed.json()["tokens"]["refresh_token"]
    assert rotated_refresh_token != original_refresh_token

    reused = await tenancy_client.post(
        "/api/v1/access/refresh",
        json={"refresh_token": original_refresh_token},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_token_reuse_detected"


async def test_invited_user_without_role_is_permission_denied(
    tenancy_client: AsyncClient,
) -> None:
    tenant_id = await create_tenant(tenancy_client, "access-invite")
    registered = await register_admin(
        tenancy_client,
        tenant_id,
        email="invite-admin@prepsuite.io",
    )
    admin_token = registered["tokens"]["access_token"]

    invitation = await tenancy_client.post(
        "/api/v1/access/invitations",
        headers=bearer(admin_token),
        json={"tenant_id": tenant_id, "email": "learner@prepsuite.io"},
    )
    assert invitation.status_code == 201, invitation.text
    invitation_token = invitation.json()["invitation_token"]

    accepted = await tenancy_client.post(
        "/api/v1/access/invitations/accept",
        json={
            "token": invitation_token,
            "password": "correct-horse-battery",
            "first_name": "Learner",
        },
    )
    assert accepted.status_code == 200, accepted.text
    invited_token = accepted.json()["tokens"]["access_token"]

    matrix = await tenancy_client.get(
        "/api/v1/access/permission-matrix",
        headers=bearer(invited_token),
    )
    assert matrix.status_code == 403
    assert matrix.json()["error"]["code"] == "permission_denied"


async def test_password_reset_and_login_rate_limit(tenancy_client: AsyncClient) -> None:
    tenant_id = await create_tenant(tenancy_client, "access-reset")
    await register_admin(
        tenancy_client,
        tenant_id,
        email="reset@prepsuite.io",
        password="original-password",
    )

    reset_request = await tenancy_client.post(
        "/api/v1/access/password-reset/request",
        json={"tenant_id": tenant_id, "email": "reset@prepsuite.io"},
    )
    assert reset_request.status_code == 200, reset_request.text
    reset_token = reset_request.json()["reset_token"]
    assert reset_token

    reset_confirm = await tenancy_client.post(
        "/api/v1/access/password-reset/confirm",
        json={"token": reset_token, "new_password": "updated-password"},
    )
    assert reset_confirm.status_code == 204, reset_confirm.text

    login = await tenancy_client.post(
        "/api/v1/access/login",
        headers={"X-Tenant-ID": tenant_id},
        json={"email": "reset@prepsuite.io", "password": "updated-password"},
    )
    assert login.status_code == 200, login.text

    for _ in range(5):
        failed = await tenancy_client.post(
            "/api/v1/access/login",
            headers={"X-Tenant-ID": tenant_id, "X-Forwarded-For": "203.0.113.10"},
            json={"email": "reset@prepsuite.io", "password": "wrong-password"},
        )
        assert failed.status_code == 401

    limited = await tenancy_client.post(
        "/api/v1/access/login",
        headers={"X-Tenant-ID": tenant_id, "X-Forwarded-For": "203.0.113.10"},
        json={"email": "reset@prepsuite.io", "password": "wrong-password"},
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "login_rate_limited"
