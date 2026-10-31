"""Database engine and sessions (async SQLAlchemy 2 on psycopg 3).

The engine is created once in the app's lifespan (``app.main``) and stored on
``app.state``; endpoints get a session through the ``get_session`` dependency.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the async engine. No connection is opened until the first query.

    ``pool_pre_ping`` replaces connections the database closed in the meantime
    (e.g. after a PostgreSQL restart). ``TimeZone=UTC`` makes PostgreSQL return
    every ``timestamptz`` in UTC, whatever the server's own time zone is.
    """
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c TimeZone=UTC"},
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory for ``engine``.

    ``expire_on_commit=False``: objects stay readable after a commit. With async
    sessions an expired attribute can't be lazy-loaded, so reading it would fail.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed afterwards.

    The session doesn't commit by itself. Code that writes opens a transaction
    with ``async with session.begin():``, which commits at the end of the block
    and rolls back if it raises.
    """
    async with request.app.state.sessionmaker() as session:
        yield session
