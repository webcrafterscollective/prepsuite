from __future__ import annotations

from app.core.config import Environment, Settings


def test_settings_defaults_are_local_development_friendly() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == Environment.LOCAL
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.resolved_celery_broker_url == settings.redis_url
