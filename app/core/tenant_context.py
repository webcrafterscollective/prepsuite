from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

TenantSource = Literal["unresolved", "header", "subdomain", "authenticated_user"]


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID | None
    source: TenantSource = "unresolved"


async def get_tenant_context() -> TenantContext:
    return TenantContext(tenant_id=None)
