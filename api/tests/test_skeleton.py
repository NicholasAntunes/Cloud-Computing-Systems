"""Task 2 (skeleton): config, health, docs and the error format of docs/API.md.

Error handlers are tested through routes added by the test (``configure``), so these
tests don't depend on the file endpoints of task 4.
"""

from __future__ import annotations

import logging

import pytest
from helpers import BLOB_CONNECTION_STRING, assert_error, make_settings

from app import storage

# --- config ------------------------------------------------------------------


def test_max_upload_bytes_is_mebibytes():
    assert make_settings(max_upload_mb=1).max_upload_bytes == 1024 * 1024
    assert make_settings(max_upload_mb=100).max_upload_bytes == 100 * 1024 * 1024


def test_storage_settings_built_from_env_names():
    s = make_settings(blob_container="files").storage_settings()
    assert isinstance(s, storage.StorageSettings)
    assert s.auth == "connection_string"
    assert s.connection_string == BLOB_CONNECTION_STRING
    assert s.container == "files"


def test_settings_read_from_environment(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/x")
    monkeypatch.setenv("MAX_UPLOAD_MB", "7")
    monkeypatch.setenv("STORAGE_AUTH", "connection_string")
    monkeypatch.setenv("BLOB_CONNECTION_STRING", BLOB_CONNECTION_STRING)
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    monkeypatch.setenv("ADMIN_EMAIL", "root@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@db:5432/x"
    assert s.max_upload_bytes == 7 * 1024 * 1024
    assert s.admin_username == "root"


# --- health and docs ---------------------------------------------------------


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_swagger_ui_under_api(client):
    r = await client.get("/api/docs")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_every_route_starts_with_api(client):
    r = await client.get("/api/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/api/health" in paths
    assert all(p.startswith("/api/") for p in paths), list(paths)


# --- error format ------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_route_is_not_found(client):
    assert_error(await client.get("/api/nope"), 404, "NOT_FOUND")


@pytest.mark.asyncio
async def test_wrong_method_is_method_not_allowed(client):
    assert_error(await client.delete("/api/health"), 405, "METHOD_NOT_ALLOWED")


@pytest.mark.asyncio
async def test_validation_error_has_details_per_field(make_client):
    def configure(app):
        @app.get("/api/test/validate")
        async def validate(n: int, m: int):
            return {"n": n, "m": m}

    async with make_client(configure=configure) as client:
        r = await client.get("/api/test/validate?n=abc")
    error = assert_error(r, 400, "VALIDATION_ERROR")
    assert {d["field"] for d in error["details"]} == {"n", "m"}


@pytest.mark.asyncio
async def test_api_error_is_returned_as_given(make_client):
    from app.errors import ApiError

    def configure(app):
        @app.get("/api/test/conflict")
        async def conflict():
            raise ApiError(409, "CONFLICT", "Someone else was faster.")

    async with make_client(configure=configure) as client:
        r = await client.get("/api/test/conflict")
    error = assert_error(r, 409, "CONFLICT")
    assert error["message"] == "Someone else was faster."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (storage.FileTooLarge("too big"), 413, "FILE_TOO_LARGE"),
        (storage.BlobNotFound("gone"), 404, "NOT_FOUND"),
        (storage.StorageError("azurite down"), 503, "STORAGE_UNAVAILABLE"),
    ],
)
async def test_storage_errors_are_mapped(make_client, exc, status, code):
    def configure(app):
        @app.get("/api/test/storage")
        async def fail():
            raise exc

    async with make_client(configure=configure) as client:
        r = await client.get("/api/test/storage")
    error = assert_error(r, status, code)
    assert str(exc) not in error["message"]  # internal text never reaches the client


@pytest.mark.asyncio
async def test_unexpected_error_is_500_without_internals(make_client, caplog):
    def configure(app):
        @app.get("/api/test/boom")
        async def boom():
            raise RuntimeError("secret internal detail")

    caplog.set_level(logging.ERROR)
    async with make_client(configure=configure) as client:
        r = await client.get("/api/test/boom")
    assert_error(r, 500, "INTERNAL_ERROR")
    assert "secret internal detail" not in r.text
    assert "Traceback" not in r.text
    # ...but the stack trace is logged.
    assert any(rec.exc_info and rec.exc_info[0] is RuntimeError for rec in caplog.records)
