from __future__ import annotations

from httpx import AsyncClient


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


async def seed_catalog(client: AsyncClient) -> None:
    response = await client.post("/api/v1/platform/app-catalog/seed")
    assert response.status_code == 200, response.text


async def enable_app(client: AsyncClient, tenant_id: str, app_code: str) -> None:
    await seed_catalog(client)
    response = await client.put(
        f"/api/v1/platform/tenants/{tenant_id}/apps/{app_code}",
        json={"status": "enabled", "subscription_status": "active", "config": {}},
    )
    assert response.status_code == 200, response.text


async def register_admin(
    client: AsyncClient,
    tenant_id: str,
    *,
    email: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/access/register-institution-admin",
        json={
            "tenant_id": tenant_id,
            "email": email,
            "password": "correct-horse-battery",
            "first_name": "Learn",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def provision_learn_tenant(
    client: AsyncClient,
    slug: str,
    *,
    email: str,
    with_dependencies: bool = False,
) -> tuple[str, dict[str, str]]:
    tenant_id = await create_tenant(client, slug)
    await enable_app(client, tenant_id, "preplearn")
    if with_dependencies:
        await enable_app(client, tenant_id, "prepstudents")
        await enable_app(client, tenant_id, "preppeople")
    registered = await register_admin(client, tenant_id, email=email)
    return tenant_id, bearer(registered["tokens"]["access_token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_batch(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/batches",
        headers=headers,
        json={
            "name": "PrepLearn Batch",
            "code": "preplearn-batch-2026",
            "start_date": "2026-04-28",
            "capacity": 30,
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_teacher(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/people/employees",
        headers=headers,
        json={
            "employee_code": "LEARN-T-001",
            "first_name": "Leena",
            "last_name": "Teacher",
            "email": "learn-teacher@prepsuite.io",
            "employee_type": "teacher",
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_course(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str = "Algebra Foundations",
    slug: str = "algebra-foundations",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/learn/courses",
        headers=headers,
        json={
            "title": title,
            "slug": slug,
            "description": "Core algebra sequence.",
            "category": "math",
            "level": "foundation",
            "visibility": "private",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_module(
    client: AsyncClient,
    headers: dict[str, str],
    course_id: str,
    title: str,
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/learn/courses/{course_id}/modules",
        headers=headers,
        json={"title": title},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_lesson(
    client: AsyncClient,
    headers: dict[str, str],
    module_id: str,
    title: str,
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/learn/modules/{module_id}/lessons",
        headers=headers,
        json={
            "title": title,
            "lesson_type": "video",
            "content": {"video_id": title.lower().replace(" ", "-")},
            "duration_minutes": 20,
            "resources": [
                {
                    "title": f"{title} notes",
                    "resource_type": "document",
                    "storage_key": f"courses/{module_id}/{title}.pdf",
                    "metadata": {"printable": True},
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_course_curriculum_publish_reorder_and_assignments(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_learn_tenant(
        tenancy_client,
        "learn-life",
        email="learn-life@prepsuite.io",
        with_dependencies=True,
    )
    batch = await create_batch(tenancy_client, headers)
    teacher = await create_teacher(tenancy_client, headers)
    course = await create_course(tenancy_client, headers)
    course_id = course["id"]

    duplicate = await tenancy_client.post(
        "/api/v1/learn/courses",
        headers=headers,
        json={"title": "Duplicate", "slug": "algebra-foundations"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "course_conflict"

    listed = await tenancy_client.get(
        "/api/v1/learn/courses",
        headers=headers,
        params={"search": "algebra", "status": "draft"},
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [course_id]

    publish_empty = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/publish",
        headers=headers,
        json={},
    )
    assert publish_empty.status_code == 409
    assert publish_empty.json()["error"]["code"] == "course_publish_requirements_not_met"

    module_one = await create_module(tenancy_client, headers, course_id, "Linear Equations")
    module_two = await create_module(tenancy_client, headers, course_id, "Inequalities")
    lesson_one = await create_lesson(tenancy_client, headers, module_one["id"], "Solving Basics")
    lesson_two = await create_lesson(tenancy_client, headers, module_one["id"], "Word Problems")

    publish_with_empty_module = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/publish",
        headers=headers,
        json={},
    )
    assert publish_with_empty_module.status_code == 409
    assert publish_with_empty_module.json()["error"]["details"]["module_id"] == module_two["id"]

    lesson_three = await create_lesson(tenancy_client, headers, module_two["id"], "Graphing")

    reordered = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/reorder",
        headers=headers,
        json={
            "modules": [
                {"module_id": module_two["id"], "order_index": 1},
                {"module_id": module_one["id"], "order_index": 2},
            ],
            "lessons": [
                {"lesson_id": lesson_two["id"], "order_index": 1},
                {"lesson_id": lesson_one["id"], "order_index": 2},
            ],
        },
    )
    assert reordered.status_code == 200, reordered.text
    assert [item["id"] for item in reordered.json()["modules"]] == [
        module_two["id"],
        module_one["id"],
    ]
    second_module_lessons = reordered.json()["modules"][1]["lessons"]
    assert [item["id"] for item in second_module_lessons] == [lesson_two["id"], lesson_one["id"]]

    assigned_batch = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/assign-batch",
        headers=headers,
        json={"batch_id": batch["id"]},
    )
    assert assigned_batch.status_code == 201, assigned_batch.text
    assert assigned_batch.json()["batch_id"] == batch["id"]

    assigned_teacher = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/assign-teacher",
        headers=headers,
        json={"teacher_id": teacher["id"]},
    )
    assert assigned_teacher.status_code == 201, assigned_teacher.text
    assert assigned_teacher.json()["teacher_id"] == teacher["id"]

    published = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/publish",
        headers=headers,
        json={"notes": "Ready for students"},
    )
    assert published.status_code == 200, published.text
    published_payload = published.json()
    assert published_payload["course"]["status"] == "published"
    assert published_payload["course"]["published_at"] is not None
    assert len(published_payload["publish_history"]) == 1
    assert len(published_payload["batches"]) == 1
    assert len(published_payload["teachers"]) == 1
    assert published_payload["modules"][0]["lessons"][0]["id"] == lesson_three["id"]

    outline = await tenancy_client.get(
        f"/api/v1/learn/courses/{course_id}/outline",
        headers=headers,
    )
    assert outline.status_code == 200, outline.text
    assert outline.json()["course"]["id"] == course_id
    assert len(outline.json()["modules"]) == 2

    archived = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/archive",
        headers=headers,
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"

    publish_archived = await tenancy_client.post(
        f"/api/v1/learn/courses/{course_id}/publish",
        headers=headers,
        json={},
    )
    assert publish_archived.status_code == 409
    assert publish_archived.json()["error"]["code"] == "course_archived"


async def test_learn_app_gate_permission_and_tenant_isolation(
    tenancy_client: AsyncClient,
) -> None:
    tenant_without_app = await create_tenant(tenancy_client, "learn-disabled")
    disabled_registered = await register_admin(
        tenancy_client,
        tenant_without_app,
        email="learn-disabled@prepsuite.io",
    )
    disabled = await tenancy_client.get(
        "/api/v1/learn/courses",
        headers=bearer(disabled_registered["tokens"]["access_token"]),
    )
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "app_disabled"

    tenant_id, admin_headers = await provision_learn_tenant(
        tenancy_client,
        "learn-permission",
        email="learn-permission-admin@prepsuite.io",
    )
    invitation = await tenancy_client.post(
        "/api/v1/access/invitations",
        headers=admin_headers,
        json={"tenant_id": tenant_id, "email": "learn-no-role@prepsuite.io"},
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
        "/api/v1/learn/courses",
        headers=bearer(accepted.json()["tokens"]["access_token"]),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    _, tenant_a_headers = await provision_learn_tenant(
        tenancy_client,
        "learn-tenant-a",
        email="learn-tenant-a@prepsuite.io",
    )
    _, tenant_b_headers = await provision_learn_tenant(
        tenancy_client,
        "learn-tenant-b",
        email="learn-tenant-b@prepsuite.io",
    )
    tenant_b_course = await create_course(
        tenancy_client,
        tenant_b_headers,
        title="Tenant B Course",
        slug="tenant-b-course",
    )
    cross_tenant = await tenancy_client.get(
        f"/api/v1/learn/courses/{tenant_b_course['id']}",
        headers=tenant_a_headers,
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "course_not_found"
