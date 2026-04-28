from __future__ import annotations

from decimal import Decimal

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
            "first_name": "Question",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def provision_question_tenant(
    client: AsyncClient,
    slug: str,
    *,
    email: str,
) -> tuple[str, dict[str, str]]:
    tenant_id = await create_tenant(client, slug)
    await enable_app(client, tenant_id, "prepquestion")
    registered = await register_admin(client, tenant_id, email=email)
    return tenant_id, bearer(registered["tokens"]["access_token"])


async def create_topic(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str = "Algebra",
    slug: str = "algebra",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/questions/topics",
        headers=headers,
        json={"name": name, "slug": slug, "description": "Core algebra topic."},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_mcq(
    client: AsyncClient,
    headers: dict[str, str],
    topic_id: str,
    *,
    body: str = "What is x if x + 2 = 5?",
    marks: str = "2.00",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/questions",
        headers=headers,
        json={
            "topic_id": topic_id,
            "question_type": "mcq",
            "difficulty": "easy",
            "bloom_level": "apply",
            "body": body,
            "explanation": "Subtract 2 from both sides.",
            "marks": marks,
            "negative_marks": "0.50",
            "metadata": {"source": "manual"},
            "tags": [" Algebra ", "linear", "algebra"],
            "options": [
                {"label": "A", "body": "3", "is_correct": True},
                {"label": "B", "body": "5", "is_correct": False},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_question_bank_set_builder_and_ai_generation(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_question_tenant(
        tenancy_client,
        "question-life",
        email="question-life@prepsuite.io",
    )
    topic = await create_topic(tenancy_client, headers)

    duplicate_topic = await tenancy_client.post(
        "/api/v1/questions/topics",
        headers=headers,
        json={"name": "Duplicate Algebra", "slug": "algebra"},
    )
    assert duplicate_topic.status_code == 409
    assert duplicate_topic.json()["error"]["code"] == "question_topic_conflict"

    invalid_mcq = await tenancy_client.post(
        "/api/v1/questions",
        headers=headers,
        json={
            "topic_id": topic["id"],
            "question_type": "mcq",
            "body": "Invalid MCQ",
            "options": [
                {"label": "A", "body": "One", "is_correct": False},
                {"label": "B", "body": "Two", "is_correct": False},
            ],
        },
    )
    assert invalid_mcq.status_code == 422
    assert invalid_mcq.json()["error"]["code"] == "invalid_question_options"

    question_one = await create_mcq(tenancy_client, headers, topic["id"])
    assert question_one["status"] == "draft"
    assert question_one["tags"] == ["algebra", "linear"]
    assert question_one["metadata"]["source"] == "manual"

    reviewed = await tenancy_client.patch(
        f"/api/v1/questions/{question_one['id']}",
        headers=headers,
        json={"status": "reviewed"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "reviewed"

    approved = await tenancy_client.patch(
        f"/api/v1/questions/{question_one['id']}",
        headers=headers,
        json={"status": "approved"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    listed = await tenancy_client.get(
        "/api/v1/questions",
        headers=headers,
        params={"search": "x + 2", "status": "approved", "tag": "algebra"},
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [question_one["id"]]

    question_two = await create_mcq(
        tenancy_client,
        headers,
        topic["id"],
        body="What is y if 2y = 8?",
        marks="1.00",
    )
    question_set = await tenancy_client.post(
        "/api/v1/question-sets",
        headers=headers,
        json={"title": "Algebra Set A", "description": "Two quick checks."},
    )
    assert question_set.status_code == 201, question_set.text
    set_id = question_set.json()["id"]

    first_item_detail = await tenancy_client.post(
        f"/api/v1/question-sets/{set_id}/items",
        headers=headers,
        json={"question_id": question_one["id"], "marks_override": "3.00"},
    )
    assert first_item_detail.status_code == 201, first_item_detail.text
    assert Decimal(first_item_detail.json()["question_set"]["total_marks"]) == Decimal("3.00")

    second_item_detail = await tenancy_client.post(
        f"/api/v1/question-sets/{set_id}/items",
        headers=headers,
        json={"question_id": question_two["id"]},
    )
    assert second_item_detail.status_code == 201, second_item_detail.text
    set_payload = second_item_detail.json()
    assert Decimal(set_payload["question_set"]["total_marks"]) == Decimal("4.00")
    assert set_payload["question_set"]["difficulty_distribution"] == {"easy": 2}

    duplicate_item = await tenancy_client.post(
        f"/api/v1/question-sets/{set_id}/items",
        headers=headers,
        json={"question_id": question_two["id"]},
    )
    assert duplicate_item.status_code == 409
    assert duplicate_item.json()["error"]["code"] == "question_set_item_conflict"

    items = set_payload["items"]
    reordered = await tenancy_client.patch(
        f"/api/v1/question-sets/{set_id}/reorder",
        headers=headers,
        json={
            "items": [
                {"item_id": items[1]["id"], "order_index": 1},
                {"item_id": items[0]["id"], "order_index": 2},
            ]
        },
    )
    assert reordered.status_code == 200, reordered.text
    assert [item["question_id"] for item in reordered.json()["items"]] == [
        question_two["id"],
        question_one["id"],
    ]

    ai_job = await tenancy_client.post(
        "/api/v1/questions/ai-generation-jobs",
        headers=headers,
        json={
            "prompt": "Generate algebra substitution questions",
            "topic": "AI Algebra",
            "difficulty": "medium",
            "question_type": "mcq",
            "count": 2,
        },
    )
    assert ai_job.status_code == 201, ai_job.text
    assert ai_job.json()["status"] == "completed"
    assert len(ai_job.json()["output"]["questions"]) == 2

    approved_job = await tenancy_client.post(
        f"/api/v1/questions/ai-generation-jobs/{ai_job.json()['id']}/approve",
        headers=headers,
        json={"selected_indexes": [0], "status": "reviewed"},
    )
    assert approved_job.status_code == 200, approved_job.text
    approved_payload = approved_job.json()
    assert approved_payload["job"]["status"] == "approved"
    assert len(approved_payload["questions"]) == 1
    assert approved_payload["questions"][0]["metadata"]["source"] == "ai_generation"

    repeat_approval = await tenancy_client.post(
        f"/api/v1/questions/ai-generation-jobs/{ai_job.json()['id']}/approve",
        headers=headers,
        json={},
    )
    assert repeat_approval.status_code == 409
    assert repeat_approval.json()["error"]["code"] == "ai_generation_already_reviewed"


async def test_question_app_gate_permission_and_tenant_isolation(
    tenancy_client: AsyncClient,
) -> None:
    tenant_without_app = await create_tenant(tenancy_client, "question-disabled")
    disabled_registered = await register_admin(
        tenancy_client,
        tenant_without_app,
        email="question-disabled@prepsuite.io",
    )
    disabled = await tenancy_client.get(
        "/api/v1/questions",
        headers=bearer(disabled_registered["tokens"]["access_token"]),
    )
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "app_disabled"

    tenant_id, admin_headers = await provision_question_tenant(
        tenancy_client,
        "question-permission",
        email="question-permission-admin@prepsuite.io",
    )
    invitation = await tenancy_client.post(
        "/api/v1/access/invitations",
        headers=admin_headers,
        json={"tenant_id": tenant_id, "email": "question-no-role@prepsuite.io"},
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
        "/api/v1/questions",
        headers=bearer(accepted.json()["tokens"]["access_token"]),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    _, tenant_a_headers = await provision_question_tenant(
        tenancy_client,
        "question-tenant-a",
        email="question-tenant-a@prepsuite.io",
    )
    _, tenant_b_headers = await provision_question_tenant(
        tenancy_client,
        "question-tenant-b",
        email="question-tenant-b@prepsuite.io",
    )
    tenant_b_topic = await create_topic(
        tenancy_client,
        tenant_b_headers,
        name="Tenant B Topic",
        slug="tenant-b-topic",
    )
    tenant_b_question = await create_mcq(
        tenancy_client,
        tenant_b_headers,
        tenant_b_topic["id"],
        body="Tenant B only question",
    )
    cross_tenant = await tenancy_client.get(
        f"/api/v1/questions/{tenant_b_question['id']}",
        headers=tenant_a_headers,
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "question_not_found"
