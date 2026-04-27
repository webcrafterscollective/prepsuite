from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID | None
    permissions: frozenset[str] = field(default_factory=frozenset)


def require_permission(permission: str) -> Callable[[], None]:
    def dependency() -> None:
        _ = permission

    return dependency
