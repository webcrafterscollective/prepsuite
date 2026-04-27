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


async def enable_students_app(client: AsyncClient, tenant_id: str) -> None:
    await seed_catalog(client)
    response = await client.put(
        f"/api/v1/platform/tenants/{tenant_id}/apps/prepstudents",
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
            "first_name": "Student",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def provision_students_tenant(
    client: AsyncClient,
    slug: str,
    *,
    email: str,
) -> tuple[str, dict[str, str]]:
    tenant_id = await create_tenant(client, slug)
    await enable_students_app(client, tenant_id)
    registered = await register_admin(client, tenant_id, email=email)
    token = registered["tokens"]["access_token"]
    return tenant_id, bearer(token)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_student(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    admission_no: str,
    first_name: str = "Asha",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/students",
        headers=headers,
        json={
            "admission_no": admission_no,
            "first_name": first_name,
            "last_name": "Learner",
            "email": f"{admission_no.lower()}@students.prepsuite.io",
            "phone": "+15555550123",
            "date_of_birth": "2012-05-01",
            "gender": "female",
            "joined_at": "2026-04-28T08:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_student_lifecycle_profile_timeline_and_soft_delete(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_students_tenant(
        tenancy_client,
        "students-life",
        email="students-life@prepsuite.io",
    )

    student = await create_student(tenancy_client, headers, admission_no="ADM-1001")
    student_id = student["id"]

    duplicate = await tenancy_client.post(
        "/api/v1/students",
        headers=headers,
        json={"admission_no": "ADM-1001", "first_name": "Duplicate"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "student_conflict"

    listed = await tenancy_client.get(
        "/api/v1/students",
        headers=headers,
        params={"search": "asha", "status": "active", "limit": 10},
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [student_id]

    updated = await tenancy_client.patch(
        f"/api/v1/students/{student_id}",
        headers=headers,
        json={"status": "suspended", "status_change_reason": "fee follow-up"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "suspended"

    guardian = await tenancy_client.post(
        f"/api/v1/students/{student_id}/guardians",
        headers=headers,
        json={
            "first_name": "Mira",
            "last_name": "Guardian",
            "email": "mira.guardian@prepsuite.io",
            "phone": "+15555550199",
            "relationship_type": "mother",
            "metadata": {"preferred_language": "en"},
            "is_primary": True,
            "can_pickup": True,
            "emergency_contact": True,
        },
    )
    assert guardian.status_code == 201, guardian.text
    assert guardian.json()["guardian"]["metadata"]["preferred_language"] == "en"

    note = await tenancy_client.post(
        f"/api/v1/students/{student_id}/notes",
        headers=headers,
        json={"body": "Needs transport support.", "note_type": "ops"},
    )
    assert note.status_code == 201, note.text

    document = await tenancy_client.post(
        f"/api/v1/students/{student_id}/documents",
        headers=headers,
        json={
            "title": "Birth Certificate",
            "document_type": "identity",
            "storage_key": "tenant/students/adm-1001/birth-certificate.pdf",
            "metadata": {"verified": False},
        },
    )
    assert document.status_code == 201, document.text
    assert document.json()["metadata"]["verified"] is False

    enrollment = await tenancy_client.post(
        f"/api/v1/students/{student_id}/enrollments",
        headers=headers,
        json={"course_id": str(uuid.uuid4())},
    )
    assert enrollment.status_code == 201, enrollment.text

    profile = await tenancy_client.get(f"/api/v1/students/{student_id}/profile", headers=headers)
    assert profile.status_code == 200, profile.text
    profile_payload = profile.json()
    assert profile_payload["student"]["id"] == student_id
    assert len(profile_payload["guardians"]) == 1
    assert len(profile_payload["notes"]) == 1
    assert len(profile_payload["documents"]) == 1
    assert len(profile_payload["enrollments"]) == 1
    assert any(item["to_status"] == "suspended" for item in profile_payload["status_history"])

    timeline = await tenancy_client.get(f"/api/v1/students/{student_id}/timeline", headers=headers)
    assert timeline.status_code == 200, timeline.text
    event_types = {item["event_type"] for item in timeline.json()}
    assert {"student.created", "student.status_changed", "student.note_added"} <= event_types

    deleted = await tenancy_client.delete(f"/api/v1/students/{student_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    missing = await tenancy_client.get(f"/api/v1/students/{student_id}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "student_not_found"


async def test_batch_capacity_assignment_and_removal(tenancy_client: AsyncClient) -> None:
    _, headers = await provision_students_tenant(
        tenancy_client,
        "students-batch",
        email="students-batch@prepsuite.io",
    )
    first_student = await create_student(tenancy_client, headers, admission_no="BATCH-001")
    second_student = await create_student(
        tenancy_client,
        headers,
        admission_no="BATCH-002",
        first_name="Ben",
    )

    batch = await tenancy_client.post(
        "/api/v1/batches",
        headers=headers,
        json={
            "name": "Morning Batch",
            "code": "morning-2026",
            "start_date": "2026-04-28",
            "capacity": 1,
            "status": "active",
        },
    )
    assert batch.status_code == 201, batch.text
    batch_id = batch.json()["id"]

    assigned = await tenancy_client.post(
        f"/api/v1/batches/{batch_id}/students",
        headers=headers,
        json={"student_id": first_student["id"]},
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["status"] == "active"

    full = await tenancy_client.post(
        f"/api/v1/batches/{batch_id}/students",
        headers=headers,
        json={"student_id": second_student["id"]},
    )
    assert full.status_code == 409
    assert full.json()["error"]["code"] == "batch_capacity_exceeded"

    filtered = await tenancy_client.get(
        "/api/v1/students",
        headers=headers,
        params={"batch_id": batch_id},
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["id"] for item in filtered.json()["items"]] == [first_student["id"]]

    removed = await tenancy_client.delete(
        f"/api/v1/batches/{batch_id}/students/{first_student['id']}",
        headers=headers,
    )
    assert removed.status_code == 204, removed.text

    assigned_second = await tenancy_client.post(
        f"/api/v1/batches/{batch_id}/students",
        headers=headers,
        json={"student_id": second_student["id"]},
    )
    assert assigned_second.status_code == 201, assigned_second.text
    assert assigned_second.json()["student_id"] == second_student["id"]


async def test_bulk_import_reports_duplicates_without_aborting_successes(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_students_tenant(
        tenancy_client,
        "students-import",
        email="students-import@prepsuite.io",
    )

    response = await tenancy_client.post(
        "/api/v1/students/bulk-import",
        headers=headers,
        json={
            "students": [
                {"admission_no": "IMP-001", "first_name": "One"},
                {"admission_no": "IMP-002", "first_name": "Two"},
                {"admission_no": "IMP-001", "first_name": "Duplicate"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["admission_no"] for item in payload["created"]] == ["IMP-001", "IMP-002"]
    assert payload["errors"][0]["code"] == "duplicate_in_payload"


async def test_student_app_gate_permission_and_tenant_isolation(
    tenancy_client: AsyncClient,
) -> None:
    tenant_without_app = await create_tenant(tenancy_client, "students-disabled")
    disabled_registered = await register_admin(
        tenancy_client,
        tenant_without_app,
        email="students-disabled@prepsuite.io",
    )
    disabled = await tenancy_client.get(
        "/api/v1/students",
        headers=bearer(disabled_registered["tokens"]["access_token"]),
    )
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "app_disabled"

    tenant_id, admin_headers = await provision_students_tenant(
        tenancy_client,
        "students-permission",
        email="students-permission-admin@prepsuite.io",
    )
    invitation = await tenancy_client.post(
        "/api/v1/access/invitations",
        headers=admin_headers,
        json={"tenant_id": tenant_id, "email": "students-no-role@prepsuite.io"},
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
        "/api/v1/students",
        headers=bearer(accepted.json()["tokens"]["access_token"]),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    _, tenant_a_headers = await provision_students_tenant(
        tenancy_client,
        "students-tenant-a",
        email="students-tenant-a@prepsuite.io",
    )
    _, tenant_b_headers = await provision_students_tenant(
        tenancy_client,
        "students-tenant-b",
        email="students-tenant-b@prepsuite.io",
    )
    tenant_b_student = await create_student(
        tenancy_client,
        tenant_b_headers,
        admission_no="TENANT-B-001",
    )
    cross_tenant = await tenancy_client.get(
        f"/api/v1/students/{tenant_b_student['id']}",
        headers=tenant_a_headers,
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["error"]["code"] == "student_not_found"
