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
            "first_name": "Assess",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def provision_assess_tenant(
    client: AsyncClient,
    slug: str,
    *,
    email: str,
    with_dependencies: bool = True,
) -> tuple[str, dict[str, str]]:
    tenant_id = await create_tenant(client, slug)
    await enable_app(client, tenant_id, "prepassess")
    if with_dependencies:
        await enable_app(client, tenant_id, "prepquestion")
        await enable_app(client, tenant_id, "prepstudents")
    registered = await register_admin(client, tenant_id, email=email)
    return tenant_id, bearer(registered["tokens"]["access_token"])


async def create_student(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    admission_no: str = "ASM-001",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/students",
        headers=headers,
        json={
            "admission_no": admission_no,
            "first_name": "Anika",
            "last_name": "Student",
            "email": f"{admission_no.lower()}@prepsuite.io",
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_topic(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/questions/topics",
        headers=headers,
        json={"name": "Assessment Algebra", "slug": "assessment-algebra"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_question(
    client: AsyncClient,
    headers: dict[str, str],
    topic_id: str,
    *,
    body: str,
    question_type: str,
    marks: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "topic_id": topic_id,
        "question_type": question_type,
        "difficulty": "easy",
        "body": body,
        "marks": marks,
        "negative_marks": "0.00",
        "tags": ["assessment"],
    }
    if question_type == "mcq":
        payload["options"] = [
            {"label": "A", "body": "3", "is_correct": True},
            {"label": "B", "body": "4", "is_correct": False},
        ]
    response = await client.post("/api/v1/questions", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def create_question_set(
    client: AsyncClient,
    headers: dict[str, str],
    question_ids: list[str],
) -> dict[str, object]:
    created = await client.post(
        "/api/v1/question-sets",
        headers=headers,
        json={"title": "Assessment Set A"},
    )
    assert created.status_code == 201, created.text
    set_id = created.json()["id"]
    detail: dict[str, object] | None = None
    for question_id in question_ids:
        added = await client.post(
            f"/api/v1/question-sets/{set_id}/items",
            headers=headers,
            json={"question_id": question_id},
        )
        assert added.status_code == 201, added.text
        detail = added.json()
    assert detail is not None
    return detail


async def create_assessment_from_set(
    client: AsyncClient,
    headers: dict[str, str],
    question_set_id: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/assessments",
        headers=headers,
        json={
            "title": "Algebra Quiz 1",
            "type": "quiz",
            "question_set_id": question_set_id,
            "duration_minutes": 45,
            "settings": {"shuffle_questions": False},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_assessment_attempt_evaluation_and_results_flow(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_assess_tenant(
        tenancy_client,
        "assess-life",
        email="assess-life@prepsuite.io",
    )
    student = await create_student(tenancy_client, headers)
    topic = await create_topic(tenancy_client, headers)
    mcq = await create_question(
        tenancy_client,
        headers,
        topic["id"],
        body="What is x if x + 2 = 5?",
        question_type="mcq",
        marks="2.00",
    )
    short_answer = await create_question(
        tenancy_client,
        headers,
        topic["id"],
        body="Explain why subtracting two works.",
        question_type="short_answer",
        marks="3.00",
    )
    question_set = await create_question_set(
        tenancy_client,
        headers,
        [mcq["id"], short_answer["id"]],
    )
    assessment = await create_assessment_from_set(
        tenancy_client,
        headers,
        question_set["question_set"]["id"],
    )
    assessment_id = assessment["assessment"]["id"]
    assert Decimal(assessment["assessment"]["total_marks"]) == Decimal("5.00")
    assert len(assessment["questions"]) == 2

    listed = await tenancy_client.get(
        "/api/v1/assessments",
        headers=headers,
        params={"search": "Algebra", "status": "draft"},
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [assessment_id]

    scheduled = await tenancy_client.post(
        f"/api/v1/assessments/{assessment_id}/schedule",
        headers=headers,
        json={
            "starts_at": "2026-01-01T00:00:00+00:00",
            "ends_at": "2027-01-01T00:00:00+00:00",
            "duration_minutes": 45,
        },
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["status"] == "scheduled"

    published = await tenancy_client.post(
        f"/api/v1/assessments/{assessment_id}/publish",
        headers=headers,
        json={},
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "live"

    started = await tenancy_client.post(
        f"/api/v1/assessments/{assessment_id}/attempts/start",
        headers=headers,
        json={"student_id": student["id"], "idempotency_key": "start-1"},
    )
    assert started.status_code == 201, started.text
    attempt_id = started.json()["id"]

    repeat_start = await tenancy_client.post(
        f"/api/v1/assessments/{assessment_id}/attempts/start",
        headers=headers,
        json={"student_id": student["id"], "idempotency_key": "start-1"},
    )
    assert repeat_start.status_code == 201
    assert repeat_start.json()["id"] == attempt_id

    detail = await tenancy_client.get(f"/api/v1/assessments/{assessment_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    questions = detail.json()["questions"]
    mcq_assessment_question = next(
        item for item in questions if item["question"]["question_type"] == "mcq"
    )
    short_assessment_question = next(
        item for item in questions if item["question"]["question_type"] == "short_answer"
    )
    correct_option_id = next(
        option["id"]
        for option in mcq_assessment_question["question"]["options"]
        if option["is_correct"]
    )

    mcq_answer = await tenancy_client.post(
        f"/api/v1/assessment-attempts/{attempt_id}/answers",
        headers=headers,
        json={
            "assessment_question_id": mcq_assessment_question["id"],
            "answer": {"option_ids": [correct_option_id]},
            "idempotency_key": "answer-mcq",
        },
    )
    assert mcq_answer.status_code == 201, mcq_answer.text
    assert mcq_answer.json()["status"] == "auto_evaluated"
    assert Decimal(mcq_answer.json()["score"]) == Decimal("2.00")

    repeat_answer = await tenancy_client.post(
        f"/api/v1/assessment-attempts/{attempt_id}/answers",
        headers=headers,
        json={
            "assessment_question_id": mcq_assessment_question["id"],
            "answer": {"option_ids": [correct_option_id]},
            "idempotency_key": "answer-mcq",
        },
    )
    assert repeat_answer.status_code == 201
    assert repeat_answer.json()["id"] == mcq_answer.json()["id"]

    manual_answer = await tenancy_client.post(
        f"/api/v1/assessment-attempts/{attempt_id}/answers",
        headers=headers,
        json={
            "assessment_question_id": short_assessment_question["id"],
            "answer": {"text": "Because equality is preserved."},
            "idempotency_key": "answer-short",
        },
    )
    assert manual_answer.status_code == 201, manual_answer.text
    assert manual_answer.json()["status"] == "pending"

    submitted = await tenancy_client.post(
        f"/api/v1/assessment-attempts/{attempt_id}/submit",
        headers=headers,
        json={"idempotency_key": "submit-1"},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    queue = await tenancy_client.get(
        f"/api/v1/assessments/{assessment_id}/evaluation-queue",
        headers=headers,
    )
    assert queue.status_code == 200, queue.text
    assert [item["answer"]["id"] for item in queue.json()] == [manual_answer.json()["id"]]

    evaluated = await tenancy_client.post(
        f"/api/v1/assessment-answers/{manual_answer.json()['id']}/evaluate",
        headers=headers,
        json={"score": "2.50", "comment": "Good explanation."},
    )
    assert evaluated.status_code == 200, evaluated.text
    assert evaluated.json()["status"] == "manual_evaluated"

    publish_results = await tenancy_client.post(
        f"/api/v1/assessments/{assessment_id}/results/publish",
        headers=headers,
    )
    assert publish_results.status_code == 200, publish_results.text
    result_payload = publish_results.json()
    assert result_payload["assessment"]["status"] == "published"
    assert Decimal(result_payload["results"][0]["score"]) == Decimal("4.50")
    assert result_payload["results"][0]["status"] == "published"

    analytics = await tenancy_client.get(
        f"/api/v1/assessments/{assessment_id}/analytics",
        headers=headers,
    )
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["attempts_started"] == 1
    assert analytics.json()["attempts_evaluated"] == 1
    assert Decimal(analytics.json()["average_score"]) == Decimal("4.50")


async def test_assess_app_gate_permission_and_tenant_isolation(
    tenancy_client: AsyncClient,
) -> None:
    tenant_without_app = await create_tenant(tenancy_client, "assess-disabled")
    disabled_registered = await register_admin(
        tenancy_client,
        tenant_without_app,
        email="assess-disabled@prepsuite.io",
    )
    disabled = await tenancy_client.get(
        "/api/v1/assessments",
        headers=bearer(disabled_registered["tokens"]["access_token"]),
    )
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "app_disabled"

    tenant_id, admin_headers = await provision_assess_tenant(
        tenancy_client,
        "assess-permission",
        email="assess-permission-admin@prepsuite.io",
        with_dependencies=False,
    )
    invitation = await tenancy_client.post(
        "/api/v1/access/invitations",
        headers=admin_headers,
        json={"tenant_id": tenant_id, "email": "assess-no-role@prepsuite.io"},
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
        "/api/v1/assessments",
        headers=bearer(accepted.json()["tokens"]["access_token"]),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    _, tenant_a_headers = await provision_assess_tenant(
        tenancy_client,
        "assess-tenant-a",
        email="assess-tenant-a@prepsuite.io",
    )
    _, tenant_b_headers = await provision_assess_tenant(
        tenancy_client,
        "assess-tenant-b",
        email="assess-tenant-b@prepsuite.io",
    )
    tenant_b_topic = await create_topic(tenancy_client, tenant_b_headers)
    tenant_b_question = await create_question(
        tenancy_client,
        tenant_b_headers,
        tenant_b_topic["id"],
        body="Tenant B question",
        question_type="mcq",
        marks="1.00",
    )
    tenant_b_set = await create_question_set(
        tenancy_client,
        tenant_b_headers,
        [tenant_b_question["id"]],
    )
    tenant_b_assessment = await create_assessment_from_set(
        tenancy_client,
        tenant_b_headers,
        tenant_b_set["question_set"]["id"],
    )
    cross_tenant = await tenancy_client.get(
        f"/api/v1/assessments/{tenant_b_assessment['assessment']['id']}",
        headers=tenant_a_headers,
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "assessment_not_found"
