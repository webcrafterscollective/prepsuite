from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.cache import check_redis_ready
from app.core.config import Settings, get_settings
from app.core.database import check_database_ready, dispose_engine
from app.core.exceptions import ErrorResponse, PrepSuiteError, install_exception_handlers
from app.core.logging import RequestIDMiddleware, StructuredAccessLogMiddleware, configure_logging
from app.modules.access.router import router as access_router
from app.modules.people.router import router as people_router
from app.modules.settings.router import router as settings_router
from app.modules.students.router import router as students_router
from app.modules.tenancy.router import platform_router, tenant_router

ReadinessChecker = Callable[[], Awaitable[dict[str, bool]]]


async def default_readiness_checker(settings: Settings) -> dict[str, bool]:
    return {
        "database": await check_database_ready(settings),
        "redis": await check_redis_ready(settings),
    }


def create_app(
    settings: Settings | None = None,
    readiness_checker: ReadinessChecker | None = None,
) -> FastAPI:
    current_settings = settings or get_settings()
    configure_logging(current_settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Any:
        yield
        await dispose_engine()

    app = FastAPI(
        title=current_settings.app_name,
        version="0.1.0",
        debug=current_settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{current_settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    install_exception_handlers(app)
    app.add_middleware(StructuredAccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware, header_name=current_settings.request_id_header)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=current_settings.cors_origins,
        allow_credentials=current_settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if current_settings.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=current_settings.trusted_hosts)

    router = APIRouter(prefix=current_settings.api_v1_prefix, tags=["System"])

    @router.get("/health", name="system:health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": current_settings.app_name,
            "environment": current_settings.environment.value,
        }

    @router.get(
        "/ready",
        name="system:ready",
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
    )
    async def ready() -> dict[str, object]:
        checker = readiness_checker or (lambda: default_readiness_checker(current_settings))
        checks = await checker()
        if not all(checks.values()):
            raise PrepSuiteError(
                "service_not_ready",
                "Service dependencies are not ready.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                details={"checks": checks},
            )
        return {"status": "ready", "checks": checks}

    app.include_router(router)
    app.include_router(access_router, prefix=current_settings.api_v1_prefix)
    app.include_router(people_router, prefix=current_settings.api_v1_prefix)
    app.include_router(settings_router, prefix=current_settings.api_v1_prefix)
    app.include_router(students_router, prefix=current_settings.api_v1_prefix)
    app.include_router(platform_router, prefix=current_settings.api_v1_prefix)
    app.include_router(tenant_router, prefix=current_settings.api_v1_prefix)
    return app


app = create_app()
