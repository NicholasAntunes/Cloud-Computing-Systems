"""The first admin account and the ``current_user`` dependency."""

from __future__ import annotations

import logging

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import User

from .passwords import hash_password

logger = logging.getLogger(__name__)


async def ensure_admin(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> None:
    """Create the admin from ``ADMIN_*`` if the ``users`` table is empty.

    Runs at every startup. As soon as any user exists it does nothing, so a
    restart never adds a second admin or resets a password, even if ``ADMIN_*``
    changed. ``ON CONFLICT DO NOTHING`` covers two API instances starting at once.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: the database can't be reached or the tables
            don't exist yet (run ``alembic upgrade head``).
    """
    async with sessionmaker() as session, session.begin():
        if await session.scalar(select(User.id).limit(1)) is not None:
            return
        password_hash = await hash_password(settings.admin_password.get_secret_value())
        created = await session.scalar(
            insert(User)
            .values(
                username=settings.admin_username,
                email=settings.admin_email,
                password_hash=password_hash,
                role="admin",
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=[User.username])
            .returning(User.id)
        )
    if created is not None:
        logger.info("Created the admin user %r", settings.admin_username)


async def current_user(request: Request) -> User:
    """FastAPI dependency: the user making the request.

    Phase 1 has no login, so this is always the first active admin. In Phase 2
    it reads the access token instead; the endpoints don't change.

    The lookup uses its own short session rather than the request's
    ``get_session``. Otherwise the request's transaction, and a pooled database
    connection, would stay open while an upload streams to Blob Storage. The
    returned ``User`` is detached but fully loaded: read its fields and use
    ``user.id`` for foreign keys.

    Raises:
        RuntimeError: there is no active admin (answered as 500 ``INTERNAL_ERROR``).
    """
    async with request.app.state.sessionmaker() as session:
        user = await session.scalar(
            select(User)
            .where(User.role == "admin", User.is_active.is_(True))
            .order_by(User.id)
            .limit(1)
        )
    if user is None:
        raise RuntimeError("No active admin user; one is created at startup.")
    return user
