from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import Depends

from app.core.exceptions import PrepSuiteError


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID | None
    permissions: frozenset[str] = field(default_factory=frozenset)


def require_permission(permission: str) -> Callable[..., object]:
    from app.modules.access.dependencies import get_current_principal

    current_principal_dependency = Depends(get_current_principal)

    async def dependency(
        principal: Principal = current_principal_dependency,
    ) -> Principal:
        if permission not in principal.permissions:
            raise PrepSuiteError(
                "permission_denied",
                "You do not have permission to perform this action.",
                status_code=403,
                details={"permission": permission},
            )
        return principal

    return dependency
