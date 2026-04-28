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
            "first_name": "Attend",
            "last_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def provision_attend_tenant(
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
        await enable_app(client, tenant_id, "prepattend")
    registered = await register_admin(client, tenant_id, email=email)
    return tenant_id, bearer(registered["tokens"]["access_token"])


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
            "name": "Attendance Batch",
            "code": "attend-2026",
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
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/batches/{batch_id}/students",
        headers=headers,
        json={"student_id": student_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_employee(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    employee_code: str = "EMP-ATT-001",
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


async def test_student_attendance_mark_summary_and_correction(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_attend_tenant(
        tenancy_client,
        "attend-students",
        email="attend-students@prepsuite.io",
    )
    first_student = await create_student(
        tenancy_client,
        headers,
        admission_no="ATT-001",
        first_name="Asha",
    )
    second_student = await create_student(
        tenancy_client,
        headers,
        admission_no="ATT-002",
        first_name="Ben",
    )
    batch = await create_batch(tenancy_client, headers)
    await add_student_to_batch(tenancy_client, headers, batch["id"], first_student["id"])
    await add_student_to_batch(tenancy_client, headers, batch["id"], second_student["id"])

    session = await tenancy_client.post(
        "/api/v1/attend/student-sessions",
        headers=headers,
        json={"batch_id": batch["id"], "date": "2026-04-28", "status": "open"},
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]

    records = await tenancy_client.post(
        f"/api/v1/attend/student-sessions/{session_id}/records",
        headers=headers,
        json={
            "submit_session": True,
            "records": [
                {"student_id": first_student["id"], "status": "present"},
                {"student_id": second_student["id"], "status": "absent", "remarks": "No call"},
            ],
        },
    )
    assert records.status_code == 201, records.text
    record_payloads = records.json()
    absent_record = next(item for item in record_payloads if item["status"] == "absent")

    summary = await tenancy_client.get(
        "/api/v1/attend/students/summary",
        headers=headers,
        params={
            "start_date": "2026-04-28",
            "end_date": "2026-04-28",
            "batch_id": batch["id"],
        },
    )
    assert summary.status_code == 200, summary.text
    by_student = {item["student_id"]: item for item in summary.json()["items"]}
    assert Decimal(by_student[first_student["id"]]["attendance_percentage"]) == Decimal("100.00")
    assert Decimal(by_student[second_student["id"]]["attendance_percentage"]) == Decimal("0.00")

    correction = await tenancy_client.post(
        "/api/v1/attend/correction-requests",
        headers=headers,
        json={
            "target_type": "student_record",
            "student_record_id": absent_record["id"],
            "requested_status": "excused",
            "reason": "Medical note received.",
        },
    )
    assert correction.status_code == 201, correction.text
    approved = await tenancy_client.post(
        f"/api/v1/attend/correction-requests/{correction.json()['id']}/approve",
        headers=headers,
        json={"approved": True, "reviewer_note": "Approved by admin."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    corrected = await tenancy_client.get(
        "/api/v1/attend/students/summary",
        headers=headers,
        params={
            "start_date": "2026-04-28",
            "end_date": "2026-04-28",
            "student_id": second_student["id"],
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["items"][0]["excused_count"] == 1
    assert Decimal(corrected.json()["items"][0]["attendance_percentage"]) == Decimal("100.00")


async def test_employee_attendance_check_in_out_and_summary(
    tenancy_client: AsyncClient,
) -> None:
    _, headers = await provision_attend_tenant(
        tenancy_client,
        "attend-employees",
        email="attend-employees@prepsuite.io",
    )
    employee = await create_employee(tenancy_client, headers)

    check_in = await tenancy_client.post(
        "/api/v1/attend/employees/check-in",
        headers=headers,
        json={
            "employee_id": employee["id"],
            "check_in_at": "2026-04-28T09:00:00Z",
            "idempotency_key": "checkin-1",
        },
    )
    assert check_in.status_code == 201, check_in.text

    repeat = await tenancy_client.post(
        "/api/v1/attend/employees/check-in",
        headers=headers,
        json={
            "employee_id": employee["id"],
            "check_in_at": "2026-04-28T09:00:00Z",
            "idempotency_key": "checkin-1",
        },
    )
    assert repeat.status_code == 201
    assert repeat.json()["id"] == check_in.json()["id"]

    check_out = await tenancy_client.post(
        "/api/v1/attend/employees/check-out",
        headers=headers,
        json={
            "employee_id": employee["id"],
            "check_out_at": "2026-04-28T17:30:00Z",
            "status": "present",
        },
    )
    assert check_out.status_code == 200, check_out.text
    assert check_out.json()["check_out_at"] is not None

    summary = await tenancy_client.get(
        "/api/v1/attend/employees/summary",
        headers=headers,
        params={
            "start_date": "2026-04-28",
            "end_date": "2026-04-28",
            "employee_id": employee["id"],
        },
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["items"][0]["present_count"] == 1
    assert summary.json()["items"][0]["total_work_seconds"] == 30600


async def test_attend_app_gate_permission_and_tenant_isolation(
    tenancy_client: AsyncClient,
) -> None:
    tenant_id, headers = await provision_attend_tenant(
        tenancy_client,
        "attend-secure-a",
        email="attend-secure-a@prepsuite.io",
    )
    _, disabled_headers = await provision_attend_tenant(
        tenancy_client,
        "attend-disabled",
        email="attend-disabled@prepsuite.io",
        enabled=False,
    )
    gated = await tenancy_client.get(
        "/api/v1/attend/students/summary",
        headers=disabled_headers,
        params={"start_date": "2026-04-28", "end_date": "2026-04-28"},
    )
    assert gated.status_code == 403
    assert gated.json()["error"]["code"] == "app_disabled"

    accepted = await invite_and_accept_user(
        tenancy_client,
        headers,
        tenant_id,
        email="attend-no-role@prepsuite.io",
    )
    denied = await tenancy_client.get(
        "/api/v1/attend/students/summary",
        headers=bearer(accepted["tokens"]["access_token"]),
        params={"start_date": "2026-04-28", "end_date": "2026-04-28"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    student = await create_student(tenancy_client, headers, admission_no="ISO-001")
    batch = await create_batch(tenancy_client, headers)
    await add_student_to_batch(tenancy_client, headers, batch["id"], student["id"])
    session = await tenancy_client.post(
        "/api/v1/attend/student-sessions",
        headers=headers,
        json={"batch_id": batch["id"], "date": "2026-04-28"},
    )
    record = await tenancy_client.post(
        f"/api/v1/attend/student-sessions/{session.json()['id']}/records",
        headers=headers,
        json={"records": [{"student_id": student["id"], "status": "present"}]},
    )
    assert record.status_code == 201, record.text

    _, other_headers = await provision_attend_tenant(
        tenancy_client,
        "attend-secure-b",
        email="attend-secure-b@prepsuite.io",
    )
    isolated = await tenancy_client.patch(
        f"/api/v1/attend/student-records/{record.json()[0]['id']}",
        headers=other_headers,
        json={"status": "absent"},
    )
    assert isolated.status_code == 404
    assert isolated.json()["error"]["code"] == "student_attendance_record_not_found"
