from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Environment, Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_name="PrepSuite Test",
        environment=Environment.TEST,
        debug=False,
        database_url="postgresql+asyncpg://prepsuite:prepsuite@localhost:5432/prepsuite",
        redis_url="redis://localhost:6379/0",
        cors_origins=["http://testserver"],
        trusted_hosts=["testserver", "localhost", "127.0.0.1"],
        log_level="WARNING",
    )


@pytest.fixture
def ready_checker() -> Callable[[], Awaitable[dict[str, bool]]]:
    async def checker() -> dict[str, bool]:
        return {"database": True, "redis": True}

    return checker


@pytest.fixture
def app(settings: Settings, ready_checker: Callable[[], Awaitable[dict[str, bool]]]) -> FastAPI:
    return create_app(settings=settings, readiness_checker=ready_checker)


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client
