from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import build_engine, build_engine_options, build_session_factory


async def test_async_session_factory_can_be_constructed(settings: Settings) -> None:
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    session = session_factory()

    try:
        assert isinstance(session, AsyncSession)
    finally:
        await session.close()
        await engine.dispose()


def test_engine_options_include_pool_safety(settings: Settings) -> None:
    options = build_engine_options(settings)

    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == settings.database_pool_size
