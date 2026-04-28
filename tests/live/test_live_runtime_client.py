from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.config import Environment, Settings
from app.core.exceptions import PrepSuiteError
from app.modules.live.integration import LiveRuntimeClient


async def test_live_runtime_client_calls_join_contract() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        assert request.headers["authorization"] == "Bearer access-token"
        assert request.url.path == "/rooms/algebra-live-abc123/join"
        return httpx.Response(
            201,
            json={
                "room": {"class_code": "algebra-live-abc123"},
                "participant": {"id": str(uuid.uuid4())},
                "router_rtp_capabilities": {"codecs": []},
            },
        )

    client = LiveRuntimeClient(
        Settings(
            environment=Environment.TEST,
            live_api_url="http://live-api.test",
        ),
        transport=httpx.MockTransport(handler),
    )

    payload = await client.join_room(
        class_code="algebra-live-abc123",
        access_token="access-token",
        payload={"display_name": "Asha Learner", "participant_role": "student"},
    )

    assert payload["router_rtp_capabilities"] == {"codecs": []}
    assert len(seen_requests) == 1


async def test_live_runtime_client_maps_live_api_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"code": "sfu_unavailable"}})

    client = LiveRuntimeClient(
        Settings(environment=Environment.TEST, live_api_url="http://live-api.test"),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PrepSuiteError) as exc_info:
        await client.get_room(class_code="algebra-live-abc123", access_token="access-token")

    assert exc_info.value.code == "live_runtime_unavailable"
    assert exc_info.value.status_code == 503
