from __future__ import annotations

from pydantic import BaseModel, Field


class CursorPaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None


class CursorPage[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
