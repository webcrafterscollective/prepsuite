from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PrepSuiteError
from app.core.tenant_context import TenantContext
from app.modules.tenancy.dependencies import get_tenant_scoped_session, require_tenant_context
from app.modules.tenancy.service import TenantService

TenantContextDep = Annotated[TenantContext, Depends(require_tenant_context)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_scoped_session)]


def require_app_enabled(app_code: str) -> Callable[..., object]:
    async def dependency(
        context: TenantContextDep,
        session: TenantSessionDep,
    ) -> None:
        if not await TenantService(session).is_app_enabled(context, app_code):
            raise PrepSuiteError(
                "app_disabled",
                f"The {app_code} app is not enabled for this tenant.",
                status_code=403,
                details={"app_code": app_code},
            )

    return dependency
