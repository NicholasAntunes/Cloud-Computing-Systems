"""Writing LogBook entries (docs/API.md "LogBook service" and "LogEntry").

Three pieces, as agreed with role A:

* ``log_event`` — a **success**. The entry joins the caller's transaction, next
  to the change it records: committed with the operation or rolled back with
  it, so the LogBook never says "uploaded" for an upload that didn't happen.
* ``log_failure`` — a **failure**. Written in its own short session and
  committed at once, because the caller's transaction is usually being rolled
  back at that moment and would take the entry with it. It never raises.
* ``logged(action)`` — a route dependency that records which action the route
  is. A's error handlers read it back with ``logged_action(request)`` and call
  ``log_failure``, so no endpoint can forget its failure entry.
"""

from __future__ import annotations

import json
import logging
import uuid
from enum import StrEnum
from typing import Any

from fastapi import Depends, Request, params
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LogEntry, User

logger = logging.getLogger(__name__)


class Action(StrEnum):
    """What happened; the table in docs/API.md "LogEntry" says which route writes it.

    A failed operation keeps its own action with ``success=false`` (e.g. a refused
    ``UPLOAD``). Only logins have a separate one, ``LOGIN_FAILED``, which A's rate
    limit counts.
    """

    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    LIST = "LIST"
    UPLOAD = "UPLOAD"
    UPDATE = "UPDATE"  # a new version of an existing file
    DOWNLOAD = "DOWNLOAD"
    RESTORE = "RESTORE"
    SHARE = "SHARE"
    DELETE = "DELETE"
    USER_CREATE = "USER_CREATE"
    USER_DEACTIVATE = "USER_DEACTIVATE"


# Column lengths of app.models.LogEntry.
_USERNAME_MAX = 50
_IP_MAX = 45
_USER_AGENT_MAX = 512

# Where ``logged`` keeps the route's action during a request.
_STATE_KEY = "log_action"


async def log_event(
    session: AsyncSession,
    request: Request,
    action: Action,
    user: User,
    *,
    file_id: uuid.UUID | None = None,
    version_no: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add a ``success=true`` entry to ``session``; the caller's commit writes it.

    Call it inside the operation's ``async with session.begin():``. If the entry
    can't be written, the commit fails and the operation with it: nothing
    happens without its entry. UUIDs and dates in ``details`` are stored as
    strings, e.g. ``{"from_version": 2}`` for ``RESTORE``.

    Raises:
        ValueError: ``action`` is not an ``Action``.
    """
    entry = _entry(
        request,
        Action(action),
        success=True,
        user=user,
        username=None,
        file_id=file_id,
        version_no=version_no,
        details=details,
    )
    session.add(entry)


async def log_failure(
    request: Request,
    action: Action,
    error: str,
    *,
    user: User | None = None,
    username: str | None = None,
    file_id: uuid.UUID | None = None,
    version_no: int | None = None,
) -> None:
    """Write a ``success=false`` entry with ``details={"error": error}`` and commit it.

    ``error`` is the API error code the client gets, e.g. ``"NOT_FOUND"``. The
    entry uses its own session (``request.app.state.sessionmaker``), so the
    rollback of the failed operation can't erase it. Pass ``user`` when the user
    is known; for a ``LOGIN_FAILED`` with an unknown name, pass ``username``
    (the name that was typed) instead.

    Never raises: if the entry can't be written (database down, a wrong
    argument), the problem goes to the server log, and the client still gets the
    error of the operation that failed.
    """
    try:
        entry = _entry(
            request,
            Action(action),
            success=False,
            user=user,
            username=username,
            file_id=file_id,
            version_no=version_no,
            details={"error": error},
        )
        async with request.app.state.sessionmaker() as session, session.begin():
            session.add(entry)
    except Exception:
        logger.exception("Could not write the LogBook entry for a failed %s", action)


def logged(action: Action) -> params.Depends:
    """Route dependency that records the route's action for the error handlers.

    Use it as ``@router.post(..., dependencies=[logged(Action.UPLOAD)])``. FastAPI
    runs the decorator's dependencies before the endpoint's own (``require()``),
    so the action is known even when ``require()`` refuses the request.

    Raises:
        ValueError: ``action`` is not an ``Action`` (when the route is defined).
    """
    route_action = Action(action)

    async def record_action(request: Request) -> None:
        setattr(request.state, _STATE_KEY, route_action)

    return Depends(record_action)


def logged_action(request: Request) -> Action | None:
    """The action ``logged`` recorded for this request, or ``None`` if the route has none."""
    return getattr(request.state, _STATE_KEY, None)


def _entry(
    request: Request,
    action: Action,
    *,
    success: bool,
    user: User | None,
    username: str | None,
    file_id: uuid.UUID | None,
    version_no: int | None,
    details: dict[str, Any] | None,
) -> LogEntry:
    """The row to insert, with the client's IP and user agent from ``request``."""
    return LogEntry(
        action=action.value,
        success=success,
        user_id=user.id if user is not None else None,
        username=_clean(user.username if user is not None else username, _USERNAME_MAX),
        file_id=file_id,
        version_no=version_no,
        ip=_clean(request.client.host if request.client else None, _IP_MAX),
        user_agent=_clean(request.headers.get("user-agent"), _USER_AGENT_MAX),
        details=_json_safe(details),
    )


def _clean(value: str | None, max_length: int) -> str | None:
    """``value`` cut to its column length, without NUL characters.

    These values come from the client. Writing the entry must never fail because
    of them: for a success that would roll the operation back too. PostgreSQL
    text can't hold NUL (``\\x00``).
    """
    if value is None:
        return None
    return value.replace("\x00", "")[:max_length]


def _json_safe(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """``details`` with every value JSON can't hold (UUID, datetime, ...) as a string."""
    if details is None:
        return None
    return json.loads(json.dumps(details, default=str))
