"""Shared fixtures for the API tests (tests/test_skeleton.py, test_database.py, test_files.py).

The API tests talk to the app over HTTP only (httpx + ASGITransport), against a real
PostgreSQL and a real Azurite, and check the rules in docs/API.md. They need:

    PostgreSQL  database ``cloudfiles_test`` on 127.0.0.1:5432 (override: TEST_DATABASE_URL)
    Azurite     blob service on 127.0.0.1:10000         (override: BLOB_CONNECTION_STRING)

What the app must provide (task 1b, docs/roles/A-my-tasks.md):

    app.main.create_app(settings: Settings | None = None) -> FastAPI
        Engine and storage are created in the lifespan from ``settings``.
    app.config.Settings  pydantic-settings, field names = env var names in lower case;
        ``max_upload_bytes`` property, ``storage_settings()`` method
    app.models.Base      SQLAlchemy declarative base holding users, files, file_versions
    app.errors.ApiError(status, code, message, details=None)

App imports happen inside the fixtures, so B's storage tests still run while the
API doesn't exist yet. Tables are recreated once per test session and emptied before
every test. All tests share the blob container ``api-tests``, emptied before and after
every test (only re-exported ``app.storage`` functions are used).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import pytest_asyncio
from helpers import TEST_DATABASE_URL, make_settings

from app import storage

# --- database ----------------------------------------------------------------


@pytest.fixture(scope="session")
def db_engine():
    """Sync engine on the test database; tables recreated once per session."""
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool

    from app.models import Base

    if not make_url(TEST_DATABASE_URL).database.endswith("_test"):
        pytest.exit(f"refusing to drop tables in a non-test database: {TEST_DATABASE_URL}")
    engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine):
    """Empty all tables, then return ``run(sql, **params) -> list of row mappings``."""
    from sqlalchemy import text

    from app.models import Base

    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    if tables:
        with db_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    def run(sql: str, **params: Any) -> list[Any]:
        with db_engine.begin() as conn:
            result = conn.execute(text(sql), params)
            return list(result.mappings()) if result.returns_rows else []

    return run


# --- app and client ----------------------------------------------------------


async def _empty_container() -> None:
    for name in await storage.list_blobs():
        await storage.delete_blob(name)


@pytest_asyncio.fixture
async def make_client(db) -> AsyncIterator[Callable[..., Any]]:
    """Factory: ``async with make_client(max_upload_mb=1) as client: ...``.

    Runs the app's lifespan (startup + shutdown) around the client. ``configure``
    gets the FastAPI app before startup, e.g. to add a test-only route.
    """
    from app.main import create_app

    @asynccontextmanager
    async def factory(
        configure: Callable[[Any], None] | None = None, **overrides: Any
    ) -> AsyncIterator[httpx.AsyncClient]:
        app = create_app(make_settings(**overrides))
        if configure:
            configure(app)
        try:
            async with app.router.lifespan_context(app):
                await _empty_container()
                # raise_app_exceptions=False: get the 500 response instead of the re-raise.
                transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                    try:
                        yield c
                    finally:
                        await _empty_container()
        finally:
            await storage.close_storage()  # safe if the lifespan already closed it

    yield factory


@pytest_asyncio.fixture
async def client(make_client) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client() as c:
        yield c
