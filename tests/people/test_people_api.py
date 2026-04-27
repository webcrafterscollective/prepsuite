from __future__ import annotations

import uuid

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
            "first_name": "People",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def provision_people_tenant(
    client: AsyncClient,
    slug: str,
    *,
    email: str,
    with_students: bool = False,
) -> tuple[str, dict[str, str]]:
    tenant_id = await create_tenant(client, slug)
    await enable_app(client, tenant_id, "preppeople")
    if with_students:
        await enable_app(client, tenant_id, "prepstudents")
    registered = await register_admin(client, tenant_id, email=email)
    return tenant_id, bearer(registered["tokens"]["access_token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def invite_and_accept_user(
    client: AsyncClient,
    headers: dict[str, str],
    tenant_id: str,
    *,
    email: str,
) -> dict[str, object]:
    invitation = await client.post(
        "/api/v1/access/invitations",
        headers=headers,
        json={"tenant_id": tenant_id, "email": email},
    )
    assert invitation.status_code == 201, invitation.text
    accepted = await client.post(
        "/api/v1/access/invitations/accept",
        json={
            "token": invitation.json()["invitation_token"],
            "password": "correct-horse-battery",
            "first_name": "Linked",
            "last_name": "User",
        },
    )
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


async def create_department(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/people/departments",
        headers=headers,
        json={
            "name": "Academic Department",
            "code": "academic",
            "description": "Teachers and academic staff",
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_batch(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/batches",
        headers=headers,
        json={
            "name": "People Phase Batch",
            "code": "people-phase-2026",
            "start_date": "2026-04-28",
            "capacity": 25,
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_employee(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    employee_code: str,
    first_name: str = "Tara",
    employee_type: str = "teacher",
    department_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/people/employees",
        headers=headers,
        json={
            "user_id": user_id,
            "department_id": department_id,
            "employee_code": employee_code,
            "first_name": first_name,
            "last_name": "Faculty",
            "email": f"{employee_code.lower()}@prepsuite.io",
            "phone": "+15555550222",
            "employee_type": employee_type,
            "status": "active",
            "joined_at": "2026-04-28T08:00:00Z",
            "profile": {
                "job_title": "Senior Teacher",
                "bio": "Focuses on learner outcomes.",
                "qualifications": {"degree": "M.Ed"},
                "emergency_contact": {"name": "Emergency Contact"},
                "profile_data": {"specialization": "math"},
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_employee_directory_profile_teacher_assignment_and_workload(
    tenancy_client: AsyncClient,
) -> None:
    tenant_id, headers = await provision_people_tenant(
        tenancy_client,
        "people-life",
        email="people-life@prepsuite.io",
        with_students=True,
    )
    accepted = await invite_and_accept_user(
        tenancy_client,
        headers,
        tenant_id,
        email="teacher-linked@prepsuite.io",
    )
    linked_user_id = accepted["user"]["id"]
    department = await create_department(tenancy_client, headers)
    batch = await create_batch(tenancy_client, headers)

    employee = await create_employee(
        tenancy_client,
        headers,
        employee_code="EMP-1001",
        department_id=department["id"],
        user_id=linked_user_id,
    )
    employee_id = employee["id"]
    assert employee["user_id"] == linked_user_id
    assert employee["department_id"] == department["id"]

    duplicate = await tenancy_client.post(
        "/api/v1/people/employees",
        headers=headers,
        json={"employee_code": "EMP-1001", "first_name": "Duplicate"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "employee_conflict"

    listed = await tenancy_client.get(
        "/api/v1/people/employees",
        headers=headers,
        params={
            "search": "tara",
            "employee_type": "teacher",
            "department_id": department["id"],
        },
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [employee_id]

    updated = await tenancy_client.patch(
        f"/api/v1/people/employees/{employee_id}",
        headers=headers,
        json={
            "status": "on_leave",
            "status_change_reason": "medical leave",
            "profile": {"job_title": "Lead Teacher", "profile_data": {"focus": "algebra"}},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "on_leave"

    note = await tenancy_client.post(
        f"/api/v1/people/employees/{employee_id}/notes",
        headers=headers,
        json={"body": "Prefers morning classes.", "note_type": "schedule"},
    )
    assert note.status_code == 201, note.text

    document = await tenancy_client.post(
        f"/api/v1/people/employees/{employee_id}/documents",
        headers=headers,
        json={
            "title": "Contract",
            "document_type": "hr",
            "storage_key": "tenant/people/emp-1001/contract.pdf",
            "metadata": {"signed": True},
        },
    )
    assert document.status_code == 201, document.text
    assert document.json()["metadata"]["signed"] is True

    course_id = str(uuid.uuid4())
    assignment = await tenancy_client.post(
        "/api/v1/people/teacher-assignments",
        headers=headers,
        json={
            "teacher_id": employee_id,
            "course_id": course_id,
            "batch_id": batch["id"],
            "assignment_type": "primary",
            "starts_at": "2026-04-29T08:00:00Z",
            "ends_at": "2026-09-30T08:00:00Z",
            "status": "active",
        },
    )
    assert assignment.status_code == 201, assignment.text
    assert assignment.json()["course_id"] == course_id
    assert assignment.json()["batch_id"] == batch["id"]

    workload = await tenancy_client.get(
        f"/api/v1/people/teachers/{employee_id}/workload",
        headers=headers,
    )
    assert workload.status_code == 200, workload.text
    assert workload.json()["active_assignment_count"] == 1
    assert workload.json()["course_count"] == 1
    assert workload.json()["batch_count"] == 1

    profile = await tenancy_client.get(
        f"/api/v1/people/employees/{employee_id}/profile",
        headers=headers,
    )
    assert profile.status_code == 200, profile.text
    profile_payload = profile.json()
    assert profile_payload["department"]["id"] == department["id"]
    assert profile_payload["profile"]["job_title"] == "Lead Teacher"
    assert len(profile_payload["documents"]) == 1
    assert len(profile_payload["notes"]) == 1
    assert len(profile_payload["teacher_assignments"]) == 1
    assert any(item["to_status"] == "on_leave" for item in profile_payload["status_history"])

    timeline = await tenancy_client.get(
        f"/api/v1/people/employees/{employee_id}/timeline",
        headers=headers,
    )
    assert timeline.status_code == 200, timeline.text
    event_types = {item["event_type"] for item in timeline.json()}
    assert {
        "employee.created",
        "employee.status_changed",
        "employee.note_added",
        "teacher.assignment.created",
    } <= event_types

    accountant = await create_employee(
        tenancy_client,
        headers,
        employee_code="EMP-2001",
        first_name="Anika",
        employee_type="accountant",
    )
    not_teacher = await tenancy_client.post(
        "/api/v1/people/teacher-assignments",
        headers=headers,
        json={
            "teacher_id": accountant["id"],
            "course_id": str(uuid.uuid4()),
            "assignment_type": "primary",
        },
    )
    assert not_teacher.status_code == 422
    assert not_teacher.json()["error"]["code"] == "employee_not_teacher"


async def test_people_app_gate_permission_and_tenant_isolation(
    tenancy_client: AsyncClient,
) -> None:
    tenant_without_app = await create_tenant(tenancy_client, "people-disabled")
    disabled_registered = await register_admin(
        tenancy_client,
        tenant_without_app,
        email="people-disabled@prepsuite.io",
    )
    disabled = await tenancy_client.get(
        "/api/v1/people/employees",
        headers=bearer(disabled_registered["tokens"]["access_token"]),
    )
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "app_disabled"

    tenant_id, admin_headers = await provision_people_tenant(
        tenancy_client,
        "people-permission",
        email="people-permission-admin@prepsuite.io",
    )
    accepted = await invite_and_accept_user(
        tenancy_client,
        admin_headers,
        tenant_id,
        email="people-no-role@prepsuite.io",
    )
    denied = await tenancy_client.get(
        "/api/v1/people/employees",
        headers=bearer(accepted["tokens"]["access_token"]),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    _, tenant_a_headers = await provision_people_tenant(
        tenancy_client,
        "people-tenant-a",
        email="people-tenant-a@prepsuite.io",
    )
    _, tenant_b_headers = await provision_people_tenant(
        tenancy_client,
        "people-tenant-b",
        email="people-tenant-b@prepsuite.io",
    )
    tenant_b_employee = await create_employee(
        tenancy_client,
        tenant_b_headers,
        employee_code="TENANT-B-EMP",
    )
    cross_tenant = await tenancy_client.get(
        f"/api/v1/people/employees/{tenant_b_employee['id']}",
        headers=tenant_a_headers,
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "employee_not_found"
