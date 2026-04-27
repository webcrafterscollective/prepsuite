from __future__ import annotations

import uuid

from httpx import AsyncClient


async def create_tenant(
    client: AsyncClient,
    *,
    name: str,
    slug: str,
    domain: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": name,
            "slug": slug,
            "status": "active",
            "plan_type": "starter",
            "primary_domain": domain,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_tenant_context_resolves_by_header_slug_domain_subdomain_and_user(
    tenancy_client: AsyncClient,
) -> None:
    tenant = await create_tenant(
        tenancy_client,
        name="Acme Academy",
        slug="acme-academy",
        domain="academy.test",
    )
    tenant_id = str(tenant["id"])

    by_id = await tenancy_client.get("/api/v1/tenant/current", headers={"X-Tenant-ID": tenant_id})
    assert by_id.status_code == 200
    assert by_id.json()["tenant_id"] == tenant_id
    assert by_id.json()["source"] == "header"

    by_slug = await tenancy_client.get(
        "/api/v1/tenant/current",
        headers={"X-Tenant-Slug": "acme-academy"},
    )
    assert by_slug.status_code == 200
    assert by_slug.json()["tenant_id"] == tenant_id

    by_domain = await tenancy_client.get(
        "/api/v1/tenant/current",
        headers={"Host": "academy.test"},
    )
    assert by_domain.status_code == 200
    assert by_domain.json()["tenant_id"] == tenant_id

    by_subdomain = await tenancy_client.get(
        "/api/v1/tenant/current",
        headers={"Host": "acme-academy.prepsuite.in"},
    )
    assert by_subdomain.status_code == 200
    assert by_subdomain.json()["tenant_id"] == tenant_id

    user_id = str(uuid.uuid4())
    add_user = await tenancy_client.post(
        f"/api/v1/platform/tenants/{tenant_id}/users",
        json={"user_id": user_id, "status": "active", "is_primary_admin": True},
    )
    assert add_user.status_code == 201, add_user.text

    by_user = await tenancy_client.get("/api/v1/tenant/current", headers={"X-User-ID": user_id})
    assert by_user.status_code == 200
    assert by_user.json()["tenant_id"] == tenant_id
    assert by_user.json()["source"] == "authenticated_user"


async def test_tenant_settings_and_apps_are_scoped_to_current_tenant(
    tenancy_client: AsyncClient,
) -> None:
    seed = await tenancy_client.post("/api/v1/platform/app-catalog/seed")
    assert seed.status_code == 200

    tenant_a = await create_tenant(tenancy_client, name="Tenant A", slug="tenant-a")
    tenant_b = await create_tenant(tenancy_client, name="Tenant B", slug="tenant-b")
    tenant_a_id = str(tenant_a["id"])
    tenant_b_id = str(tenant_b["id"])

    app_payload = {
        "status": "enabled",
        "subscription_status": "active",
        "config": {"max_students": 100},
    }
    enable_a = await tenancy_client.put(
        f"/api/v1/platform/tenants/{tenant_a_id}/apps/preplearn",
        json=app_payload,
    )
    assert enable_a.status_code == 200, enable_a.text

    settings_a = await tenancy_client.patch(
        "/api/v1/tenant/settings",
        headers={"X-Tenant-ID": tenant_a_id},
        json={"timezone": "Asia/Kolkata", "general_settings": {"campus": "north"}},
    )
    assert settings_a.status_code == 200, settings_a.text
    assert settings_a.json()["tenant_id"] == tenant_a_id
    assert settings_a.json()["timezone"] == "Asia/Kolkata"

    settings_b = await tenancy_client.get(
        "/api/v1/tenant/settings",
        headers={"X-Tenant-ID": tenant_b_id},
    )
    assert settings_b.status_code == 200, settings_b.text
    assert settings_b.json()["tenant_id"] == tenant_b_id
    assert settings_b.json()["timezone"] == "UTC"

    apps_a = await tenancy_client.get("/api/v1/tenant/apps", headers={"X-Tenant-ID": tenant_a_id})
    assert apps_a.status_code == 200, apps_a.text
    assert [item["app_code"] for item in apps_a.json()] == ["preplearn"]

    apps_b = await tenancy_client.get("/api/v1/tenant/apps", headers={"X-Tenant-ID": tenant_b_id})
    assert apps_b.status_code == 200, apps_b.text
    assert apps_b.json() == []


async def test_missing_tenant_context_returns_standard_error(tenancy_client: AsyncClient) -> None:
    response = await tenancy_client.get(
        "/api/v1/tenant/current",
        headers={"X-Request-ID": "req-missing-tenant"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "tenant_required"
    assert response.json()["error"]["request_id"] == "req-missing-tenant"
