from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

logger = structlog.get_logger(__name__)
ExceptionHandler = Callable[[Request, Exception], Response | Awaitable[Response]]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class PrepSuiteError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def get_request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def build_error_response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or {},
            request_id=get_request_id(request),
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def prepsuite_error_handler(request: Request, exc: PrepSuiteError) -> JSONResponse:
    return build_error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return build_error_response(
        request,
        code="http_error",
        message=detail,
        status_code=exc.status_code,
        details={},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return build_error_response(
        request,
        code="validation_error",
        message="Request validation failed.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": exc.errors()},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", path=request.url.path, request_id=get_request_id(request))
    return build_error_response(
        request,
        code="internal_server_error",
        message="An unexpected error occurred.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details={},
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PrepSuiteError, cast(ExceptionHandler, prepsuite_error_handler))
    app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_error_handler))
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_error_handler),
    )
    app.add_exception_handler(Exception, unhandled_error_handler)
