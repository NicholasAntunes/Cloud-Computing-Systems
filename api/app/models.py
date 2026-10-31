"""Database tables (SQLAlchemy 2), see docs/PLAN.md §6.

Phase 1 tables: ``users``, ``files`` and ``file_versions``. ``file_permissions``,
``refresh_tokens`` and ``logbook`` come in Phases 2–3.

Every timestamp is ``timestamptz`` set by PostgreSQL (``now()``), so all rows share
one clock; ``app.db`` makes the connection return them in UTC. The schema itself
is created by the Alembic migrations in ``migrations/``; the tests create it from
``Base.metadata`` instead.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLES = ("viewer", "user", "admin")


class Base(DeclarativeBase):
    """Declarative base of every table; ``Base.metadata`` is what the tests create.

    The naming convention gives every constraint a fixed name, so later Alembic
    migrations can drop or change it by name.
    """

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class User(Base):
    """An account. Phase 1 only has the admin created at startup (``app.auth``)."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(254))
    # Argon2id hash in PHC format ("$argon2id$v=19$..."), never the password.
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class File(Base):
    """A file as the user sees it. Its content lives in ``file_versions`` + Blob Storage.

    ``current_version`` is the ``version_no`` of the current row in
    ``file_versions``; its ``uploaded_at`` / ``uploaded_by`` are the file's
    ``updated_at`` / ``updated_by`` in docs/API.md. Deleting sets ``deleted_at``;
    rows are never removed.
    """

    __tablename__ = "files"
    __table_args__ = (CheckConstraint("current_version >= 1", name="current_version"),)

    # Chosen by the API before the upload, because the blob name contains it.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # The name as uploaded; only ever used in Content-Disposition, never as a path.
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    current_version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileVersion(Base):
    """One uploaded version of a file, stored in the blob ``{file_id}/{version_no}``.

    ``UNIQUE (file_id, version_no)`` is the safety net for simultaneous new
    versions (Phase 5, docs/PLAN.md §6).
    """

    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint("file_id", "version_no"),
        CheckConstraint("version_no >= 1", name="version_no"),
        CheckConstraint("size_bytes >= 0", name="size_bytes"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"))
    version_no: Mapped[int]
    blob_name: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))  # hex
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
