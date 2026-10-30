"""Database tables (SQLAlchemy 2), see docs/PLAN.md §6.

The tables (users, files, file_versions) are not defined yet.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base of every table; ``Base.metadata`` is what the tests create."""
