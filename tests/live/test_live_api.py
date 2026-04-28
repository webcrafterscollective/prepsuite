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
            "first_name": "Live",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def provision_live_tenant(
    client: AsyncClient,
    slug: str,
    *,
    email: str,
    enabled: bool = True,
) -> tuple[str, dict[str, str]]:
    tenant_id = await create_tenant(client, slug)
    await enable_app(client, tenant_id, "prepstudents")
    await enable_app(client, tenant_id, "preppeople")
    if enabled:
        await enable_app(client, tenant_id, "preplive")
    registered = await register_admin(client, tenant_id, email=email)
    return tenant_id, bearer(registered["tokens"]["access_token"])


async def create_student(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    admission_no: str,
    first_name: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/students",
        headers=headers,
        json={
            "admission_no": admission_no,
            "first_name": first_name,
            "last_name": "Learner",
            "email": f"{admission_no.lower()}@students.prepsuite.io",
            "date_of_birth": "2012-05-01",
            "joined_at": "2026-04-28T08:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_batch(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/batches",
        headers=headers,
        json={
            "name": "Live Batch",
            "code": "live-2026",
            "start_date": "2026-04-28",
            "capacity": 25,
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_student_to_batch(
    client: AsyncClient,
    headers: dict[str, str],
    batch_id: str,
    student_id: str,
) -> None:
    response = await client.post(
        f"/api/v1/batches/{batch_id}/students",
        headers=headers,
        json={"student_id": student_id},
    )
    assert response.status_code == 201, response.text


async def create_teacher(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    employee_code: str = "LIVE-T-001",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/people/employees",
        headers=headers,
        json={
            "employee_code": employee_code,
            "first_name": "Tara",
            "last_name": "Faculty",
            "email": f"{employee_code.lower()}@prepsuite.io",
            "employee_type": "teacher",
            "status": "active",
            "joined_at": "2026-04-28T08:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def assign_teacher_to_batch(
    client: AsyncClient,
    headers: dict[str, str],
    teacher_id: str,
    batch_id: str,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/people/teacher-assignments",
        headers=headers,
        json={
            "teacher_id": teacher_id,
            "batch_id": batch_id,
            "assignment_type": "primary",
            "starts_at": "2026-01-01T00:00:00Z",
            "ends_at": "2027-01-01T00:00:00Z",
            "status": "active",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def schedule_live_class(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    batch_id: str,
    instructor_id: str,
    capacity: int = 2,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/live/classes",
        headers=headers,
        json={
            "title": "Algebra Live Class",
            "description": "Live practice session",
            "batch_id": batch_id,
            "instructor_id": instructor_id,
            "starts_at": "2026-01-01T00:00:00Z",
            "ends_at": "2027-01-01T00:00:00Z",
            "duration_minutes": 60,
            "capacity": capacity,
            "join_before_minutes": 30,
            "join_after_minutes": 30,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


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
            "first_name": "No",
            "last_name": "Role",
        },
    )
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


async def test_live_class_schedule_access_attendance_recording_and_end(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_live_tenant(
        tenancy_client,
        "live-flow",
        email="live-flow@prepsuite.io",
    )
    first_student = await create_student(
        tenancy_client,
        headers,
        admission_no="LIVE-001",
        first_name="Asha",
    )
    second_student = await create_student(
        tenancy_client,
        headers,
        admission_no="LIVE-002",
        first_name="Ben",
    )
    batch = await create_batch(tenancy_client, headers)
    await add_student_to_batch(tenancy_client, headers, batch["id"], first_student["id"])
    await add_student_to_batch(tenancy_client, headers, batch["id"], second_student["id"])
    teacher = await create_teacher(tenancy_client, headers)
    await assign_teacher_to_batch(tenancy_client, headers, teacher["id"], batch["id"])

    live_class = await schedule_live_class(
        tenancy_client,
        headers,
        batch_id=batch["id"],
        instructor_id=teacher["id"],
    )
    live_class_id = live_class["id"]
    class_code = live_class["class_code"]
    assert live_class["link"] == f"https://live.prepsuite.in/{class_code}"
    assert live_class["status"] == "scheduled"

    listed = await tenancy_client.get(
        "/api/v1/live/classes",
        headers=headers,
        params={"batch_id": batch["id"], "status": "scheduled"},
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [live_class_id]

    by_code = await tenancy_client.get(
        f"/api/v1/live/classes/by-code/{class_code}",
        headers=headers,
    )
    assert by_code.status_code == 200, by_code.text
    assert by_code.json()["live_class"]["id"] == live_class_id

    opened = await tenancy_client.post(
        f"/api/v1/live/classes/{live_class_id}/open",
        headers=headers,
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "open"

    allowed = await tenancy_client.post(
        f"/api/v1/live/classes/{class_code}/validate-access",
        headers=headers,
        json={"student_id": first_student["id"], "participant_role": "student"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["allowed"] is True
    participant_id = allowed.json()["participant"]["id"]

    full = await tenancy_client.post(
        f"/api/v1/live/classes/{class_code}/validate-access",
        headers=headers,
        json={"student_id": second_student["id"], "participant_role": "student"},
    )
    assert full.status_code == 200, full.text
    assert full.json()["allowed"] is False
    assert full.json()["reason"] == "class_capacity_full"

    attendance = await tenancy_client.post(
        f"/api/v1/live/classes/{live_class_id}/attendance-events",
        headers=headers,
        json={
            "events": [
                {
                    "event_type": "live.participant.left",
                    "student_id": first_student["id"],
                    "participant_role": "student",
                    "occurred_at": "2026-04-28T10:15:00Z",
                    "total_duration_seconds": 900,
                }
            ],
            "snapshot": {"participants": [participant_id]},
        },
    )
    assert attendance.status_code == 200, attendance.text
    assert attendance.json()["processed"] == 1
    assert attendance.json()["participants"][0]["total_duration_seconds"] == 900

    recording = await tenancy_client.post(
        f"/api/v1/live/classes/{live_class_id}/recordings",
        headers=headers,
        json={
            "provider_recording_id": "rec-001",
            "playback_url": "https://cdn.prepsuite.test/rec-001.mp4",
            "duration_seconds": 900,
            "status": "ready",
            "metadata": {"provider": "mediasoup"},
        },
    )
    assert recording.status_code == 201, recording.text
    assert recording.json()["status"] == "ready"

    ended = await tenancy_client.post(f"/api/v1/live/classes/{live_class_id}/end", headers=headers)
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ended"

    detail = await tenancy_client.get(f"/api/v1/live/classes/{live_class_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["recordings"]) == 1
    event_types = {item["event_type"] for item in detail.json()["events"]}
    assert {
        "live.class.scheduled",
        "live.class.started",
        "live.participant.joined",
        "live.participant.left",
        "live.recording.added",
        "live.class.ended",
    } <= event_types


async def test_live_access_denies_non_member_expired_window_and_unassigned_teacher(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_live_tenant(
        tenancy_client,
        "live-denials",
        email="live-denials@prepsuite.io",
    )
    member = await create_student(
        tenancy_client,
        headers,
        admission_no="LIVE-D-001",
        first_name="Member",
    )
    outsider = await create_student(
        tenancy_client,
        headers,
        admission_no="LIVE-D-002",
        first_name="Outsider",
    )
    batch = await create_batch(tenancy_client, headers)
    await add_student_to_batch(tenancy_client, headers, batch["id"], member["id"])
    teacher = await create_teacher(tenancy_client, headers, employee_code="LIVE-T-002")

    unassigned = await tenancy_client.post(
        "/api/v1/live/classes",
        headers=headers,
        json={
            "title": "Denied Class",
            "batch_id": batch["id"],
            "instructor_id": teacher["id"],
            "starts_at": "2026-01-01T00:00:00Z",
            "ends_at": "2027-01-01T00:00:00Z",
            "duration_minutes": 60,
            "capacity": 25,
        },
    )
    assert unassigned.status_code == 422
    assert unassigned.json()["error"]["code"] == "instructor_not_assigned"

    await assign_teacher_to_batch(tenancy_client, headers, teacher["id"], batch["id"])
    live_class = await schedule_live_class(
        tenancy_client,
        headers,
        batch_id=batch["id"],
        instructor_id=teacher["id"],
        capacity=25,
    )
    outsider_access = await tenancy_client.post(
        f"/api/v1/live/classes/{live_class['class_code']}/validate-access",
        headers=headers,
        json={"student_id": outsider["id"], "participant_role": "student"},
    )
    assert outsider_access.status_code == 200, outsider_access.text
    assert outsider_access.json()["allowed"] is False
    assert outsider_access.json()["reason"] == "student_not_in_batch"

    expired = await tenancy_client.post(
        f"/api/v1/live/classes/{live_class['class_code']}/validate-access",
        headers=headers,
        json={
            "student_id": member["id"],
            "participant_role": "student",
            "now": "2027-01-02T00:00:00Z",
        },
    )
    assert expired.status_code == 200, expired.text
    assert expired.json()["allowed"] is False
    assert expired.json()["reason"] == "join_window_closed"


async def test_live_app_gate_permission_and_tenant_isolation(
    tenancy_client: AsyncClient,
) -> None:
    tenant_id, headers = await provision_live_tenant(
        tenancy_client,
        "live-secure-a",
        email="live-secure-a@prepsuite.io",
    )
    _, disabled_headers = await provision_live_tenant(
        tenancy_client,
        "live-disabled",
        email="live-disabled@prepsuite.io",
        enabled=False,
    )
    gated = await tenancy_client.get("/api/v1/live/classes", headers=disabled_headers)
    assert gated.status_code == 403
    assert gated.json()["error"]["code"] == "app_disabled"

    accepted = await invite_and_accept_user(
        tenancy_client,
        headers,
        tenant_id,
        email="live-no-role@prepsuite.io",
    )
    denied = await tenancy_client.get(
        "/api/v1/live/classes",
        headers=bearer(accepted["tokens"]["access_token"]),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    student = await create_student(
        tenancy_client,
        headers,
        admission_no="LIVE-ISO-001",
        first_name="Iso",
    )
    batch = await create_batch(tenancy_client, headers)
    await add_student_to_batch(tenancy_client, headers, batch["id"], student["id"])
    teacher = await create_teacher(tenancy_client, headers, employee_code="LIVE-T-003")
    await assign_teacher_to_batch(tenancy_client, headers, teacher["id"], batch["id"])
    live_class = await schedule_live_class(
        tenancy_client,
        headers,
        batch_id=batch["id"],
        instructor_id=teacher["id"],
    )

    _, other_headers = await provision_live_tenant(
        tenancy_client,
        "live-secure-b",
        email="live-secure-b@prepsuite.io",
    )
    isolated = await tenancy_client.get(
        f"/api/v1/live/classes/{live_class['id']}",
        headers=other_headers,
    )
    assert isolated.status_code == 404
    assert isolated.json()["error"]["code"] == "live_class_not_found"
