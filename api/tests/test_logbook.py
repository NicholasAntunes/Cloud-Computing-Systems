"""The ``logbook`` table and ``app.logbook`` (docs/API.md "LogEntry" and "LogBook service").

The functions are called from test-only routes, because they need a real request
(client IP, ``User-Agent``) and the app's sessionmaker. The admin endpoints and
the "N operations → exactly N entries" test come with ``GET /api/logbook``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

import pytest
from fastapi import Depends, Request
from helpers import ADMIN_USERNAME
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.logbook import Action, log_event, log_failure, logged, logged_action
from app.models import User

# FastAPI resolves the route annotations (``from __future__``) in this module's
# globals, so everything the routes below use is imported or defined at the top.
CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_session)]

# Not in the files table: the logbook has no foreign keys (guessed IDs are logged).
FILE_ID = uuid.UUID("6f1c2a9e-3b7d-4e0a-9c51-2d8f0b7a4e13")
USER_AGENT = "Mozilla/5.0 (test)"

LOGBOOK_COLUMNS = {
    "id",
    "ts",
    "user_id",
    "username",
    "action",
    "file_id",
    "version_no",
    "ip",
    "user_agent",
    "success",
    "details",
}

# The action table in docs/API.md "LogEntry".
API_ACTIONS = {
    "LOGIN",
    "LOGIN_FAILED",
    "LOGOUT",
    "LIST",
    "UPLOAD",
    "UPDATE",
    "DOWNLOAD",
    "RESTORE",
    "SHARE",
    "DELETE",
    "USER_CREATE",
    "USER_DEACTIVATE",
}


class Boom(Exception):
    """Raised inside a test route's transaction to roll it back."""


def _broken_sessionmaker():
    raise OperationalError("SELECT 1", {}, Exception("the database is down"))


async def _action_seen_by_a_later_dependency(request: Request) -> Action | None:
    return logged_action(request)


ActionSeen = Annotated[Action | None, Depends(_action_seen_by_a_later_dependency)]


def routes(app) -> None:
    """Test-only routes, one per way of writing an entry."""

    @app.post("/api/test/upload")
    async def upload(request: Request, user: CurrentUser, session: DbSession):
        async with session.begin():
            await log_event(
                session,
                request,
                Action.UPLOAD,
                user,
                file_id=FILE_ID,
                version_no=1,
                details={"name": "holiday.jpg", "file_id": FILE_ID},
            )
        return {}

    @app.post("/api/test/upload-fails")
    async def upload_fails(request: Request, user: CurrentUser, session: DbSession):
        # The operation fails halfway; the failure is written while its
        # transaction is still open, then the transaction is rolled back.
        try:
            async with session.begin():
                await log_event(session, request, Action.UPLOAD, user, file_id=FILE_ID)
                await log_failure(request, Action.UPLOAD, "STORAGE_UNAVAILABLE", user=user)
                raise Boom
        except Boom:
            pass
        return {}

    @app.post("/api/test/download-refused")
    async def download_refused(request: Request, user: CurrentUser):
        await log_failure(
            request, Action.DOWNLOAD, "NOT_FOUND", user=user, file_id=FILE_ID, version_no=2
        )
        return {}

    @app.post("/api/test/login-failed")
    async def login_failed(request: Request, username: str):
        await log_failure(request, Action.LOGIN_FAILED, "INVALID_CREDENTIALS", username=username)
        return {}

    @app.post("/api/test/failure-with-bad-action")
    async def failure_with_bad_action(request: Request):
        await log_failure(request, "UPLODA", "NOT_FOUND")
        return {}

    @app.post("/api/test/database-down")
    async def database_down(request: Request):
        real = request.app.state.sessionmaker
        request.app.state.sessionmaker = _broken_sessionmaker
        try:
            await log_failure(request, Action.DOWNLOAD, "NOT_FOUND", file_id=FILE_ID)
        finally:
            request.app.state.sessionmaker = real
        return {}

    @app.get("/api/test/logged", dependencies=[logged(Action.UPLOAD)])
    async def with_action(request: Request, seen: ActionSeen):
        return {"action": logged_action(request), "seen_by_dependency": seen}

    @app.get("/api/test/not-logged")
    async def without_action(request: Request):
        return {"action": logged_action(request)}


def entries(db) -> list:
    return db("SELECT * FROM logbook ORDER BY id")


def admin_id(db) -> int:
    return db("SELECT id FROM users WHERE username = :u", u=ADMIN_USERNAME)[0]["id"]


# --- table -------------------------------------------------------------------


def test_logbook_has_the_agreed_columns(db):
    rows = db(
        "SELECT column_name, data_type, character_maximum_length AS length"
        " FROM information_schema.columns WHERE table_name = 'logbook'"
    )
    columns = {r["column_name"]: r for r in rows}
    assert LOGBOOK_COLUMNS <= set(columns)
    assert columns["ts"]["data_type"] == "timestamp with time zone"
    assert columns["file_id"]["data_type"] == "uuid"
    assert columns["details"]["data_type"] == "jsonb"
    assert columns["username"]["length"] == 50
    assert columns["ip"]["length"] == 45
    assert columns["user_agent"]["length"] == 512


def test_logbook_has_no_foreign_keys(db_engine, db):
    from sqlalchemy import inspect

    assert inspect(db_engine).get_foreign_keys("logbook") == []


def test_logbook_indexes(db_engine, db):
    from sqlalchemy import inspect

    indexes = {tuple(i["column_names"]) for i in inspect(db_engine).get_indexes("logbook")}
    assert {("ts",), ("username", "action", "ts"), ("ip", "action", "ts")} <= indexes


def test_actions_match_the_api_contract():
    assert {a.value for a in Action} == API_ACTIONS


# --- log_event (successes) ---------------------------------------------------


@pytest.mark.asyncio
async def test_success_entry_is_committed_with_the_operation(make_client, db):
    async with make_client(configure=routes) as client:
        r = await client.post("/api/test/upload", headers={"User-Agent": USER_AGENT})
    assert r.status_code == 200, r.text
    [entry] = entries(db)
    assert entry["action"] == "UPLOAD"
    assert entry["success"] is True
    assert entry["user_id"] == admin_id(db)
    assert entry["username"] == ADMIN_USERNAME
    assert entry["file_id"] == FILE_ID
    assert entry["version_no"] == 1
    assert entry["ip"] == "127.0.0.1"  # httpx's ASGITransport client address
    assert entry["user_agent"] == USER_AGENT
    assert entry["ts"] is not None
    # UUIDs in details are stored as strings.
    assert entry["details"] == {"name": "holiday.jpg", "file_id": str(FILE_ID)}


@pytest.mark.asyncio
async def test_rollback_keeps_only_the_failure_entry(make_client, db):
    async with make_client(configure=routes) as client:
        r = await client.post("/api/test/upload-fails")
    assert r.status_code == 200, r.text
    [entry] = entries(db)
    assert entry["action"] == "UPLOAD"
    assert entry["success"] is False
    assert entry["details"] == {"error": "STORAGE_UNAVAILABLE"}


# --- log_failure -------------------------------------------------------------


@pytest.mark.asyncio
async def test_failure_entry_of_a_known_user(make_client, db):
    async with make_client(configure=routes) as client:
        r = await client.post("/api/test/download-refused")
    assert r.status_code == 200, r.text
    [entry] = entries(db)
    assert entry["action"] == "DOWNLOAD"
    assert entry["success"] is False
    assert entry["user_id"] == admin_id(db)
    assert entry["username"] == ADMIN_USERNAME
    assert entry["file_id"] == FILE_ID
    assert entry["version_no"] == 2
    assert entry["details"] == {"error": "NOT_FOUND"}


@pytest.mark.asyncio
async def test_failed_login_of_an_unknown_user(make_client, db):
    async with make_client(configure=routes) as client:
        r = await client.post("/api/test/login-failed", params={"username": "mallory"})
    assert r.status_code == 200, r.text
    [entry] = entries(db)
    assert entry["action"] == "LOGIN_FAILED"
    assert entry["success"] is False
    assert entry["user_id"] is None
    assert entry["username"] == "mallory"
    assert entry["details"] == {"error": "INVALID_CREDENTIALS"}


@pytest.mark.asyncio
async def test_client_values_are_cut_to_the_column_length(make_client, db):
    async with make_client(configure=routes) as client:
        r = await client.post(
            "/api/test/login-failed",
            params={"username": "x\x00" * 100},
            headers={"User-Agent": "a" * 1000},
        )
    assert r.status_code == 200, r.text
    [entry] = entries(db)
    assert entry["username"] == "x" * 50  # NUL removed, then cut
    assert entry["user_agent"] == "a" * 512


@pytest.mark.asyncio
async def test_failure_entry_never_raises_when_the_database_is_down(make_client, db, caplog):
    caplog.set_level(logging.ERROR, logger="app.logbook.service")
    async with make_client(configure=routes) as client:
        r = await client.post("/api/test/database-down")
    assert r.status_code == 200, r.text
    assert "Could not write the LogBook entry" in caplog.text


@pytest.mark.asyncio
async def test_failure_entry_never_raises_on_a_wrong_action(make_client, db, caplog):
    caplog.set_level(logging.ERROR, logger="app.logbook.service")
    async with make_client(configure=routes) as client:
        r = await client.post("/api/test/failure-with-bad-action")
    assert r.status_code == 200, r.text
    assert entries(db) == []
    assert "Could not write the LogBook entry" in caplog.text


# --- logged ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logged_records_the_route_action_before_other_dependencies(make_client, db):
    async with make_client(configure=routes) as client:
        r = await client.get("/api/test/logged")
    assert r.status_code == 200, r.text
    # The endpoint's own dependency (like require()) already sees the action.
    assert r.json() == {"action": "UPLOAD", "seen_by_dependency": "UPLOAD"}


@pytest.mark.asyncio
async def test_route_without_logged_has_no_action(make_client, db):
    async with make_client(configure=routes) as client:
        r = await client.get("/api/test/not-logged")
    assert r.status_code == 200, r.text
    assert r.json() == {"action": None}


# --- wrong calls -------------------------------------------------------------

_REQUEST = Request({"type": "http", "method": "GET", "path": "/", "headers": []})


@pytest.mark.asyncio
async def test_log_event_rejects_an_unknown_action():
    with pytest.raises(ValueError):
        await log_event(object(), _REQUEST, "UPLODA", User(id=1, username="alice"))


def test_logged_rejects_an_unknown_action():
    with pytest.raises(ValueError):
        logged("UPLODA")
