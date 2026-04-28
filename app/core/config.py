from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREPSUITE_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PrepSuite Backend"
    environment: Environment = Environment.LOCAL
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://prepsuite_app:prepsuite_app@localhost:5432/prepsuite"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    cors_allow_credentials: bool = True
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "0.0.0.0", "prepsuite-api"]
    )

    log_level: str = "INFO"
    request_id_header: str = "X-Request-ID"
    readiness_timeout_seconds: float = 2.0

    jwt_issuer: str = "prepsuite"
    jwt_audience: str = "prepsuite-api"
    jwt_private_key_pem: str | None = None
    jwt_public_key_pem: str | None = None
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    password_reset_token_ttl_minutes: int = 30
    invitation_token_ttl_days: int = 7
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300

    live_api_url: str = "http://localhost:8010"
    live_api_timeout_seconds: float = 10.0

    @property
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
