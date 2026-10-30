"""Task 3 (database): tables as in PLAN §6 and the admin seeded at startup.

The tables are created from ``app.models.Base`` (see conftest.py); the Alembic
migration itself is checked by hand with ``alembic upgrade head``.
"""

from __future__ import annotations

import pytest
from helpers import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME

# Columns from docs/PLAN.md §6. Extra columns are allowed.
PLAN_COLUMNS = {
    "users": {"id", "username", "email", "password_hash", "role", "is_active", "created_at"},
    "files": {
        "id",
        "owner_id",
        "name",
        "content_type",
        "current_version",
        "created_at",
        "deleted_at",
    },
    "file_versions": {
        "id",
        "file_id",
        "version_no",
        "blob_name",
        "size_bytes",
        "sha256",
        "uploaded_by",
        "uploaded_at",
    },
}
TIMESTAMP_COLUMNS = {
    ("users", "created_at"),
    ("files", "created_at"),
    ("files", "deleted_at"),
    ("file_versions", "uploaded_at"),
}


def columns(db, table: str) -> dict[str, str]:
    rows = db(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :t",
        t=table,
    )
    return {r["column_name"]: r["data_type"] for r in rows}


# --- tables ------------------------------------------------------------------


@pytest.mark.parametrize("table", sorted(PLAN_COLUMNS))
def test_table_has_plan_columns(db, table):
    assert PLAN_COLUMNS[table] <= set(columns(db, table))


@pytest.mark.parametrize(("table", "column"), sorted(TIMESTAMP_COLUMNS))
def test_timestamps_are_timestamptz(db, table, column):
    assert columns(db, table)[column] == "timestamp with time zone"


def test_files_id_is_uuid(db):
    assert columns(db, "files")["id"] == "uuid"


def test_version_number_unique_per_file(db_engine, db):
    from sqlalchemy import inspect

    insp = inspect(db_engine)
    constraints = insp.get_unique_constraints("file_versions")
    indexes = [i for i in insp.get_indexes("file_versions") if i["unique"]]
    unique_sets = [set(c["column_names"]) for c in constraints + indexes]
    assert {"file_id", "version_no"} in unique_sets


# --- admin seeding -----------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_created_on_first_startup(make_client, db):
    async with make_client():
        pass
    users = db("SELECT username, email, role, is_active, password_hash FROM users")
    assert len(users) == 1
    admin = users[0]
    assert admin["username"] == ADMIN_USERNAME
    assert admin["email"] == ADMIN_EMAIL
    assert admin["role"] == "admin"
    assert admin["is_active"] is True


@pytest.mark.asyncio
async def test_admin_password_is_argon2id_hash(make_client, db):
    from argon2 import PasswordHasher

    async with make_client():
        pass
    password_hash = db("SELECT password_hash FROM users")[0]["password_hash"]
    assert password_hash.startswith("$argon2id$")
    assert ADMIN_PASSWORD not in password_hash
    assert PasswordHasher().verify(password_hash, ADMIN_PASSWORD)


@pytest.mark.asyncio
async def test_restart_does_not_create_second_admin(make_client, db):
    async with make_client():
        pass
    async with make_client():
        pass
    assert db("SELECT count(*) AS n FROM users")[0]["n"] == 1


@pytest.mark.asyncio
async def test_no_admin_seeded_when_users_exist(make_client, db):
    async with make_client():
        pass
    # A restart with other admin settings must not add or change anyone.
    async with make_client(admin_username="someone-else", admin_password="other"):
        pass
    assert [r["username"] for r in db("SELECT username FROM users")] == [ADMIN_USERNAME]
