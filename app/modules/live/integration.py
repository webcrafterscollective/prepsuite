from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, cast

import httpx
from fastapi import status

from app.core.config import Settings
from app.core.exceptions import PrepSuiteError


@dataclass(slots=True)
class LiveRuntimeClient:
    """Small client for future main-backend calls into the Live API runtime."""

    settings: Settings
    transport: httpx.AsyncBaseTransport | None = None

    @property
    def base_url(self) -> str:
        return self.settings.live_api_url.rstrip("/")

    async def get_room(self, *, class_code: str, access_token: str) -> dict[str, Any]:
        response = await self._request("GET", f"/rooms/{class_code}", access_token=access_token)
        return self._json_dict(response)

    async def join_room(
        self,
        *,
        class_code: str,
        access_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/rooms/{class_code}/join",
            access_token=access_token,
            json=payload,
        )
        return self._json_dict(response)

    async def leave_room(
        self,
        *,
        class_code: str,
        access_token: str,
        participant_id: uuid.UUID,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/rooms/{class_code}/leave",
            access_token=access_token,
            json={"participant_id": str(participant_id)},
        )
        return self._json_dict(response)

    async def start_room(
        self,
        *,
        class_code: str,
        access_token: str,
        actor_participant_id: uuid.UUID,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/rooms/{class_code}/start",
            access_token=access_token,
            json={"actor_participant_id": str(actor_participant_id)},
        )
        return self._json_dict(response)

    async def end_room(
        self,
        *,
        class_code: str,
        access_token: str,
        actor_participant_id: uuid.UUID,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/rooms/{class_code}/end",
            access_token=access_token,
            json={"actor_participant_id": str(actor_participant_id)},
        )
        return self._json_dict(response)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=self.settings.live_api_timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                json=json,
            )
        self._raise_for_live_error(response)
        return response

    def _raise_for_live_error(self, response: httpx.Response) -> None:
        if response.status_code >= 500:
            raise PrepSuiteError(
                "live_runtime_unavailable",
                "PrepSuite Live API is unavailable.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if response.status_code >= 400:
            raise PrepSuiteError(
                "live_runtime_request_failed",
                "PrepSuite Live API rejected the request.",
                status_code=response.status_code,
                details={"response": response.text},
            )

    def _json_dict(self, response: httpx.Response) -> dict[str, Any]:
        payload = response.json()
        if not isinstance(payload, dict):
            raise PrepSuiteError(
                "live_runtime_contract_invalid",
                "PrepSuite Live API returned an invalid response.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
        return cast(dict[str, Any], payload)
