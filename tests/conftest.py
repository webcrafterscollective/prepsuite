from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.core.config import Environment, Settings
from app.core.database import get_db_session
from app.main import create_app

TEST_TABLES = (
    "ai_question_generation_jobs",
    "question_set_items",
    "question_sets",
    "question_tags",
    "question_options",
    "questions",
    "question_topics",
    "course_prerequisites",
    "course_publish_history",
    "course_teachers",
    "course_batches",
    "lesson_resources",
    "lessons",
    "course_modules",
    "courses",
    "employee_status_history",
    "employee_documents",
    "employee_notes",
    "teacher_assignments",
    "employee_profiles",
    "employees",
    "departments",
    "student_status_history",
    "student_documents",
    "student_notes",
    "student_enrollments",
    "student_guardians",
    "guardians",
    "batch_students",
    "batches",
    "students",
    "invitation_tokens",
    "password_reset_tokens",
    "login_history",
    "login_sessions",
    "refresh_tokens",
    "user_roles",
    "role_permissions",
    "roles",
    "permissions",
    "user_profiles",
    "users",
    "tenant_app_settings",
    "tenant_integrations",
    "tenant_attendance_rules",
    "tenant_grading_rules",
    "tenant_academic_years",
    "tenant_users",
    "tenant_branding",
    "tenant_settings",
    "tenant_apps",
    "tenant_domains",
    "app_catalog",
    "tenants",
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_name="PrepSuite Test",
        environment=Environment.TEST,
        debug=False,
        database_url="postgresql+asyncpg://prepsuite:prepsuite@localhost:5432/prepsuite",
        redis_url="redis://localhost:6379/0",
        cors_origins=["http://testserver"],
        trusted_hosts=["testserver", "localhost", "127.0.0.1"],
        log_level="WARNING",
    )


@pytest.fixture
def ready_checker() -> Callable[[], Awaitable[dict[str, bool]]]:
    async def checker() -> dict[str, bool]:
        return {"database": True, "redis": True}

    return checker


@pytest.fixture
def app(settings: Settings, ready_checker: Callable[[], Awaitable[dict[str, bool]]]) -> FastAPI:
    return create_app(settings=settings, readiness_checker=ready_checker)


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client


@pytest.fixture(scope="session")
def postgres_database_url() -> Iterator[str]:
    with PostgresContainer(
        "postgres:16-alpine",
        username="prepsuite_test",
        password="prepsuite_test",
        dbname="prepsuite_test",
        driver="asyncpg",
    ) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def migrated_postgres_database_url(postgres_database_url: str) -> Iterator[str]:
    previous_url = os.environ.get("PREPSUITE_DATABASE_URL")
    os.environ["PREPSUITE_DATABASE_URL"] = postgres_database_url
    try:
        command.upgrade(Config("alembic.ini"), "head")
        yield postgres_database_url
    finally:
        if previous_url is None:
            os.environ.pop("PREPSUITE_DATABASE_URL", None)
        else:
            os.environ["PREPSUITE_DATABASE_URL"] = previous_url


@pytest.fixture(scope="session")
def app_database_url(migrated_postgres_database_url: str) -> Iterator[str]:
    url = make_url(migrated_postgres_database_url)
    app_url = url.set(username="prepsuite_app", password="prepsuite_app")
    owner_engine = create_async_engine(migrated_postgres_database_url, pool_pre_ping=True)

    async def grant_app_role() -> None:
        async with owner_engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    DO
                    $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT FROM pg_roles WHERE rolname = 'prepsuite_app'
                        ) THEN
                            CREATE ROLE prepsuite_app LOGIN PASSWORD 'prepsuite_app';
                        END IF;
                    END
                    $$;
                    """
                )
            )
            await connection.execute(
                text("GRANT CONNECT ON DATABASE prepsuite_test TO prepsuite_app")
            )
            await connection.execute(text("GRANT USAGE ON SCHEMA public TO prepsuite_app"))
            await connection.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                    "TO prepsuite_app"
                )
            )

    asyncio.run(grant_app_role())
    try:
        yield app_url.render_as_string(hide_password=False)
    finally:
        asyncio.run(owner_engine.dispose())


@pytest.fixture
async def db_engine(
    app_database_url: str,
    migrated_postgres_database_url: str,
) -> AsyncIterator[AsyncEngine]:
    owner_engine = create_async_engine(migrated_postgres_database_url, pool_pre_ping=True)
    table_list = ", ".join(TEST_TABLES)
    async with owner_engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE TABLE {table_list} CASCADE"))
    await owner_engine.dispose()

    engine = create_async_engine(app_database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def tenancy_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def test_ready_checker() -> dict[str, bool]:
        return {"database": True, "redis": True}

    test_settings = Settings(
        app_name="PrepSuite Tenancy Test",
        environment=Environment.TEST,
        debug=False,
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
        redis_url="redis://localhost:6379/15",
        cors_origins=["http://testserver"],
        trusted_hosts=["*"],
        log_level="WARNING",
    )
    test_app: FastAPI = create_app(settings=test_settings, readiness_checker=test_ready_checker)
    test_app.dependency_overrides[get_db_session] = override_get_db_session
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client
