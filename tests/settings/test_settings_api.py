from __future__ import annotations

from httpx import AsyncClient

from app.core.events import DomainEvent, event_dispatcher


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
    email: str = "settings-admin@prepsuite.io",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/access/register-institution-admin",
        json={
            "tenant_id": tenant_id,
            "email": email,
            "password": "correct-horse-battery",
            "first_name": "Settings",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def seed_catalog(client: AsyncClient) -> None:
    response = await client.post("/api/v1/platform/app-catalog/seed")
    assert response.status_code == 200, response.text


async def test_general_branding_grading_and_attendance_settings_emit_audit_events(
    tenancy_client: AsyncClient,
) -> None:
    tenant_id = await create_tenant(tenancy_client, "settings-general")
    registered = await register_admin(tenancy_client, tenant_id)
    token = registered["tokens"]["access_token"]
    headers = bearer(token)
    events: list[DomainEvent] = []

    async def collect(event: DomainEvent) -> None:
        if event.tenant_id is not None and str(event.tenant_id) == tenant_id:
            events.append(event)

    for event_type in (
        "prepsettings.general.updated",
        "prepsettings.branding.updated",
        "prepsettings.grading_rules.updated",
        "prepsettings.attendance_rules.updated",
    ):
        event_dispatcher.register(event_type, collect)

    general = await tenancy_client.patch(
        "/api/v1/settings/general",
        headers=headers,
        json={
            "timezone": "Asia/Kolkata",
            "locale": "en-IN",
            "general_settings": {"campus": "north"},
            "notification_preferences": {"email": True},
        },
    )
    assert general.status_code == 200, general.text
    assert general.json()["timezone"] == "Asia/Kolkata"

    branding = await tenancy_client.patch(
        "/api/v1/settings/branding",
        headers=headers,
        json={
            "logo_url": "https://cdn.prepsuite.test/logo.png",
            "primary_color": "#234567",
            "branding_settings": {"theme": "classic"},
        },
    )
    assert branding.status_code == 200, branding.text
    assert branding.json()["primary_color"] == "#234567"

    grading = await tenancy_client.patch(
        "/api/v1/settings/grading-rules",
        headers=headers,
        json={
            "name": "CBSE default",
            "pass_percentage": "35.00",
            "rounding_strategy": "nearest",
            "grade_scale": {"A": {"min": 90}, "B": {"min": 75}},
        },
    )
    assert grading.status_code == 200, grading.text
    assert grading.json()["pass_percentage"] == "35.00"

    attendance = await tenancy_client.patch(
        "/api/v1/settings/attendance-rules",
        headers=headers,
        json={
            "minimum_percentage": "75.00",
            "late_threshold_minutes": 10,
            "absent_after_minutes": 30,
            "rules": {"notify_guardian_after_absences": 3},
        },
    )
    assert attendance.status_code == 200, attendance.text
    assert attendance.json()["minimum_percentage"] == "75.00"

    assert {event.event_type for event in events} >= {
        "prepsettings.general.updated",
        "prepsettings.branding.updated",
        "prepsettings.grading_rules.updated",
        "prepsettings.attendance_rules.updated",
    }


async def test_app_toggle_respects_subscription_and_locked_state(
    tenancy_client: AsyncClient,
) -> None:
    await seed_catalog(tenancy_client)
    tenant_id = await create_tenant(tenancy_client, "settings-apps")
    registered = await register_admin(tenancy_client, tenant_id, email="apps@prepsuite.io")
    headers = bearer(registered["tokens"]["access_token"])

    subscribe_learn = await tenancy_client.put(
        f"/api/v1/platform/tenants/{tenant_id}/apps/preplearn",
        json={"status": "disabled", "subscription_status": "active", "config": {"seats": 100}},
    )
    assert subscribe_learn.status_code == 200, subscribe_learn.text

    apps_before = await tenancy_client.get("/api/v1/settings/apps", headers=headers)
    assert apps_before.status_code == 200, apps_before.text
    preplearn = next(item for item in apps_before.json() if item["app_code"] == "preplearn")
    assert preplearn["can_enable"] is True
    assert preplearn["enabled_by_tenant"] is False

    enable = await tenancy_client.patch(
        "/api/v1/settings/apps/preplearn/toggle",
        headers=headers,
        json={"enabled": True, "settings": {"visible_to_students": True}},
    )
    assert enable.status_code == 200, enable.text
    assert enable.json()["tenant_app_status"] == "enabled"
    assert enable.json()["enabled_by_tenant"] is True
    assert enable.json()["settings"]["visible_to_students"] is True

    disable = await tenancy_client.patch(
        "/api/v1/settings/apps/preplearn/toggle",
        headers=headers,
        json={"enabled": False},
    )
    assert disable.status_code == 200, disable.text
    assert disable.json()["tenant_app_status"] == "disabled"

    not_subscribed = await tenancy_client.patch(
        "/api/v1/settings/apps/prepstudents/toggle",
        headers=headers,
        json={"enabled": True},
    )
    assert not_subscribed.status_code == 403
    assert not_subscribed.json()["error"]["code"] == "app_subscription_required"

    lock_live = await tenancy_client.put(
        f"/api/v1/platform/tenants/{tenant_id}/apps/preplive",
        json={"status": "locked", "subscription_status": "active", "config": {}},
    )
    assert lock_live.status_code == 200, lock_live.text
    locked = await tenancy_client.patch(
        "/api/v1/settings/apps/preplive/toggle",
        headers=headers,
        json={"enabled": True},
    )
    assert locked.status_code == 403
    assert locked.json()["error"]["code"] == "app_locked"


async def test_academic_year_current_flag_is_exclusive(tenancy_client: AsyncClient) -> None:
    tenant_id = await create_tenant(tenancy_client, "settings-years")
    registered = await register_admin(tenancy_client, tenant_id, email="years@prepsuite.io")
    headers = bearer(registered["tokens"]["access_token"])

    year_2026 = await tenancy_client.post(
        "/api/v1/settings/academic-years",
        headers=headers,
        json={
            "name": "Academic Year 2026",
            "code": "ay-2026",
            "starts_on": "2026-04-01",
            "ends_on": "2027-03-31",
            "status": "active",
            "is_current": True,
        },
    )
    assert year_2026.status_code == 201, year_2026.text

    year_2027 = await tenancy_client.post(
        "/api/v1/settings/academic-years",
        headers=headers,
        json={
            "name": "Academic Year 2027",
            "code": "ay-2027",
            "starts_on": "2027-04-01",
            "ends_on": "2028-03-31",
            "status": "draft",
            "is_current": True,
        },
    )
    assert year_2027.status_code == 201, year_2027.text

    years = await tenancy_client.get("/api/v1/settings/academic-years", headers=headers)
    assert years.status_code == 200, years.text
    by_code = {item["code"]: item for item in years.json()}
    assert by_code["ay-2027"]["is_current"] is True
    assert by_code["ay-2026"]["is_current"] is False

    switch_back = await tenancy_client.patch(
        f"/api/v1/settings/academic-years/{year_2026.json()['id']}",
        headers=headers,
        json={"is_current": True},
    )
    assert switch_back.status_code == 200, switch_back.text

    years_after = await tenancy_client.get("/api/v1/settings/academic-years", headers=headers)
    by_code_after = {item["code"]: item for item in years_after.json()}
    assert by_code_after["ay-2026"]["is_current"] is True
    assert by_code_after["ay-2027"]["is_current"] is False


async def test_settings_permission_denied_without_role(tenancy_client: AsyncClient) -> None:
    tenant_id = await create_tenant(tenancy_client, "settings-permission")
    registered = await register_admin(
        tenancy_client,
        tenant_id,
        email="settings-owner@prepsuite.io",
    )
    admin_headers = bearer(registered["tokens"]["access_token"])

    invitation = await tenancy_client.post(
        "/api/v1/access/invitations",
        headers=admin_headers,
        json={"tenant_id": tenant_id, "email": "no-settings-role@prepsuite.io"},
    )
    assert invitation.status_code == 201, invitation.text

    accepted = await tenancy_client.post(
        "/api/v1/access/invitations/accept",
        json={
            "token": invitation.json()["invitation_token"],
            "password": "correct-horse-battery",
            "first_name": "NoRole",
        },
    )
    assert accepted.status_code == 200, accepted.text

    denied = await tenancy_client.get(
        "/api/v1/settings/general",
        headers=bearer(accepted.json()["tokens"]["access_token"]),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"
