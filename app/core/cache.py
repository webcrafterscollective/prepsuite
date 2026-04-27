from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings, get_settings


async def check_redis_ready(settings: Settings | None = None) -> bool:
    current_settings = settings or get_settings()
    client = Redis.from_url(current_settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
