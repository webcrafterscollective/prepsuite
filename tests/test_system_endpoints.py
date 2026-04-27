from __future__ import annotations

from collections.abc import Awaitable, Callable

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


async def test_health_endpoint_returns_service_metadata(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "req-health"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-health"
    assert response.json() == {
        "status": "ok",
        "service": "PrepSuite Test",
        "environment": "test",
    }


async def test_ready_endpoint_returns_dependency_checks(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": True, "redis": True}}


async def test_ready_endpoint_uses_standard_error_shape(settings: Settings) -> None:
    async def failing_checker() -> dict[str, bool]:
        return {"database": False, "redis": True}

    app = create_app(settings=settings, readiness_checker=failing_checker)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/ready", headers={"X-Request-ID": "req-ready"})

    payload = response.json()

    assert response.status_code == 503
    assert payload["error"]["code"] == "service_not_ready"
    assert payload["error"]["request_id"] == "req-ready"
    assert payload["error"]["details"] == {"checks": {"database": False, "redis": True}}


async def test_openapi_is_versioned(
    settings: Settings,
    ready_checker: Callable[[], Awaitable[dict[str, bool]]],
) -> None:
    app = create_app(settings=settings, readiness_checker=ready_checker)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "PrepSuite Test"
