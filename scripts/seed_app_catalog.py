from __future__ import annotations

import asyncio

from app.core.database import get_session_factory
from app.modules.tenancy.service import TenantService


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        seeded = await TenantService(session).seed_default_app_catalog()
        print(f"Seeded {len(seeded)} PrepSuite app catalog entries.")


if __name__ == "__main__":
    asyncio.run(main())
