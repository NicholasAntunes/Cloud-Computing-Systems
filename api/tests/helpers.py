"""Constants and helpers shared by the API tests. See conftest.py for the fixtures."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from typing import Any

import httpx

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://cloudfiles:cloudfiles@127.0.0.1:5432/cloudfiles_test",
)
BLOB_CONNECTION_STRING = os.environ.get("BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
TEST_CONTAINER = "api-tests"

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "test-admin-password"

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def make_settings(**overrides: Any):
    """Settings for one test app. ``_env_file=None`` so api/.env never leaks in."""
    from app.config import Settings

    values: dict[str, Any] = {
        "storage_auth": "connection_string",
        "blob_connection_string": BLOB_CONNECTION_STRING,
        "blob_container": TEST_CONTAINER,
        "database_url": TEST_DATABASE_URL,
        "jwt_secret": "test-jwt-secret",
        "max_upload_mb": 100,
        "admin_username": ADMIN_USERNAME,
        "admin_email": ADMIN_EMAIL,
        "admin_password": ADMIN_PASSWORD,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def assert_error(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
    """Check the status and the API.md error shape; return the ``error`` object."""
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}, body
    error = body["error"]
    assert set(error) == {"code", "message", "details"}, error
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    if code == "VALIDATION_ERROR":
        assert isinstance(error["details"], list) and error["details"]
        for item in error["details"]:
            assert set(item) == {"field", "message"}, item
    else:
        assert error["details"] is None
    return error


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def upload(
    client: httpx.AsyncClient,
    name: str = "photo.jpg",
    data: bytes | None = None,
    content_type: str = "image/jpeg",
) -> httpx.Response:
    if data is None:
        data = os.urandom(64 * 1024)
    return await client.post("/api/files", files={"file": (name, data, content_type)})


def random_uuid() -> str:
    return str(uuid.uuid4())
