"""Task 4 (file endpoints): upload, list, download and detail as in docs/API.md.

Phase 1: no login, every file belongs to the seeded admin, every permission is true.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import quote

import pytest
from helpers import ADMIN_USERNAME, ISO_UTC, assert_error, random_uuid, sha256, upload

from app import storage

FILE_KEYS = {
    "id",
    "name",
    "content_type",
    "size_bytes",
    "current_version",
    "created_at",
    "updated_at",
    "owner",
    "updated_by",
    "permissions",
}
ALL_RIGHTS = {"can_read": True, "can_update": True, "can_share": True, "can_delete": True}
MIB = 1024 * 1024


def count(db, table: str) -> int:
    return db(f"SELECT count(*) AS n FROM {table}")[0]["n"]


# --- upload ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_returns_file(client, db):
    data = os.urandom(100_000)
    r = await upload(client, "holiday.jpg", data, "image/jpeg")
    assert r.status_code == 201, r.text
    f = r.json()
    assert set(f) == FILE_KEYS
    assert str(uuid.UUID(f["id"])) == f["id"]
    assert f["name"] == "holiday.jpg"
    assert f["content_type"] == "image/jpeg"
    assert f["size_bytes"] == len(data)
    assert f["current_version"] == 1
    assert ISO_UTC.match(f["created_at"]), f["created_at"]
    assert ISO_UTC.match(f["updated_at"]), f["updated_at"]
    admin_id = db("SELECT id FROM users WHERE username = :u", u=ADMIN_USERNAME)[0]["id"]
    assert f["owner"] == {"id": admin_id, "username": ADMIN_USERNAME}
    assert f["updated_by"] == f["owner"]
    assert f["permissions"] == ALL_RIGHTS


@pytest.mark.asyncio
async def test_upload_writes_blob_and_version_1(client, db):
    data = os.urandom(10_000)
    f = (await upload(client, "../../etc/passwd", data)).json()
    # The user's file name never becomes part of the blob path.
    assert await storage.list_blobs() == [f"{f['id']}/1"]
    versions = db("SELECT * FROM file_versions")
    assert len(versions) == 1
    v = versions[0]
    assert str(v["file_id"]) == f["id"]
    assert v["version_no"] == 1
    assert v["blob_name"] == f"{f['id']}/1"
    assert v["size_bytes"] == len(data)
    assert v["sha256"] == sha256(data)


@pytest.mark.asyncio
async def test_same_name_twice_gives_two_files(client):
    a = (await upload(client, "report.pdf")).json()
    b = (await upload(client, "report.pdf")).json()
    assert a["id"] != b["id"]


@pytest.mark.asyncio
async def test_upload_without_file_field(client):
    r = await client.post("/api/files", files={"other": ("a.txt", b"hello", "text/plain")})
    error = assert_error(r, 400, "VALIDATION_ERROR")
    assert [d["field"] for d in error["details"]] == ["file"]


@pytest.mark.asyncio
async def test_upload_without_body(client):
    assert_error(await client.post("/api/files"), 400, "VALIDATION_ERROR")


@pytest.mark.asyncio
async def test_upload_empty_file(client, db):
    r = await upload(client, "empty.txt", b"", "text/plain")
    error = assert_error(r, 400, "VALIDATION_ERROR")
    assert [d["field"] for d in error["details"]] == ["file"]
    assert count(db, "files") == 0


@pytest.mark.asyncio
async def test_upload_name_of_255_characters_is_accepted(client):
    # Characters, not bytes: this name is 510 bytes in UTF-8, like files.name VARCHAR(255).
    name = "ż" * 251 + ".txt"
    r = await upload(client, name, b"x", "text/plain")
    assert r.status_code == 201, r.text
    assert r.json()["name"] == name


@pytest.mark.asyncio
async def test_upload_name_over_255_characters(client, db):
    r = await upload(client, "a" * 252 + ".txt", b"x", "text/plain")
    error = assert_error(r, 400, "VALIDATION_ERROR")
    assert [d["field"] for d in error["details"]] == ["file"]
    assert await storage.list_blobs() == []
    assert count(db, "files") == 0


@pytest.mark.asyncio
async def test_upload_exactly_at_limit_is_accepted(make_client):
    async with make_client(max_upload_mb=1) as client:
        r = await upload(client, data=os.urandom(MIB))
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_upload_far_over_limit_rejected_by_content_length(make_client, db):
    async with make_client(max_upload_mb=1) as client:
        r = await upload(client, data=os.urandom(3 * MIB))
        assert_error(r, 413, "FILE_TOO_LARGE")
        assert await storage.list_blobs() == []
    assert count(db, "files") == 0


@pytest.mark.asyncio
async def test_upload_just_over_limit_rejected_while_streaming(make_client, db):
    # Content-Length is within the multipart slack, so upload_stream's max_bytes must stop it.
    async with make_client(max_upload_mb=1) as client:
        r = await upload(client, data=os.urandom(MIB + 1))
        assert_error(r, 413, "FILE_TOO_LARGE")
        assert await storage.list_blobs() == []
    assert count(db, "files") == 0


@pytest.mark.asyncio
async def test_database_failure_deletes_blob(client, db):
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import OperationalError

    def fail_version_insert(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO FILE_VERSIONS"):
            raise OperationalError(statement, params, Exception("database went away"))

    event.listen(Engine, "before_cursor_execute", fail_version_insert)
    try:
        r = await upload(client)
    finally:
        event.remove(Engine, "before_cursor_execute", fail_version_insert)

    error = assert_error(r, 500, "INTERNAL_ERROR")
    assert "database went away" not in error["message"]
    assert await storage.list_blobs() == []
    # files and file_versions are written in one transaction.
    assert count(db, "files") == 0
    assert count(db, "file_versions") == 0


# --- list --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty(client):
    r = await client.get("/api/files")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_list_newest_first(client):
    for name in ("a.txt", "b.txt", "c.txt"):
        await upload(client, name, b"x", "text/plain")
    r = await client.get("/api/files")
    body = r.json()
    assert [f["name"] for f in body["items"]] == ["c.txt", "b.txt", "a.txt"]
    assert body["total"] == 3
    assert all(set(f) == FILE_KEYS for f in body["items"])


@pytest.mark.asyncio
async def test_list_limit_and_offset(client):
    for name in ("a.txt", "b.txt", "c.txt"):
        await upload(client, name, b"x", "text/plain")
    first = (await client.get("/api/files?limit=2")).json()
    rest = (await client.get("/api/files?limit=2&offset=2")).json()
    assert [f["name"] for f in first["items"]] == ["c.txt", "b.txt"]
    assert [f["name"] for f in rest["items"]] == ["a.txt"]
    assert first["total"] == rest["total"] == 3


@pytest.mark.asyncio
async def test_list_skips_deleted_files(client, db):
    keep = (await upload(client, "keep.txt", b"x", "text/plain")).json()
    gone = (await upload(client, "gone.txt", b"x", "text/plain")).json()
    db("UPDATE files SET deleted_at = now() WHERE id = :id", id=gone["id"])
    body = (await client.get("/api/files")).json()
    assert [f["id"] for f in body["items"]] == [keep["id"]]
    assert body["total"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["limit=1001", "limit=0", "limit=abc", "offset=-1"])
async def test_list_rejects_bad_paging(client, query):
    error = assert_error(await client.get(f"/api/files?{query}"), 400, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == query.split("=")[0]


@pytest.mark.asyncio
async def test_list_accepts_limit_1000(client):
    assert (await client.get("/api/files?limit=1000")).status_code == 200


# --- download ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_list_download_round_trip(client):
    data = os.urandom(300_000)
    uploaded = (await upload(client, "holiday.jpg", data, "image/jpeg")).json()
    listed = (await client.get("/api/files")).json()["items"]
    assert [f["id"] for f in listed] == [uploaded["id"]]

    r = await client.get(f"/api/files/{uploaded['id']}/download")
    assert r.status_code == 200
    assert sha256(r.content) == sha256(data)
    assert r.headers["content-type"].startswith("image/jpeg")
    assert r.headers["content-length"] == str(len(data))
    assert r.headers["x-content-type-options"] == "nosniff"
    disposition = r.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert 'filename="holiday.jpg"' in disposition


@pytest.mark.asyncio
async def test_download_non_ascii_name(client):
    name = "zdjęcie.jpg"
    f = (await upload(client, name)).json()
    assert f["name"] == name
    r = await client.get(f"/api/files/{f['id']}/download")
    disposition = r.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert f"filename*=UTF-8''{quote(name)}" in disposition


@pytest.mark.asyncio
async def test_download_name_cannot_break_the_header(client, db):
    # Written straight to the database: multipart parsers already mangle some of these.
    name = 'a"b\\c\r\nSet-Cookie: x=1;ż.txt'
    f = (await upload(client)).json()
    db("UPDATE files SET name = :name WHERE id = :id", name=name, id=f["id"])
    r = await client.get(f"/api/files/{f['id']}/download")
    assert r.status_code == 200
    assert r.headers["content-disposition"] == (
        'attachment; filename="a_b_c__Set-Cookie: x=1;_.txt"; '
        "filename*=UTF-8''a%22b%5Cc%0D%0ASet-Cookie%3A%20x%3D1%3B%C5%BC.txt"
    )
    assert "set-cookie" not in r.headers


@pytest.mark.asyncio
async def test_html_is_still_an_attachment(client):
    data = b"<script>alert(1)</script>"
    f = (await upload(client, "page.html", data, "text/html")).json()
    r = await client.get(f"/api/files/{f['id']}/download")
    assert r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_download_explicit_version_1(client):
    data = os.urandom(1000)
    f = (await upload(client, data=data)).json()
    r = await client.get(f"/api/files/{f['id']}/download?version=1")
    assert r.status_code == 200
    assert r.content == data


@pytest.mark.asyncio
async def test_download_missing_version(client):
    f = (await upload(client)).json()
    assert_error(await client.get(f"/api/files/{f['id']}/download?version=2"), 404, "NOT_FOUND")


@pytest.mark.asyncio
@pytest.mark.parametrize("version", ["0", "abc"])
async def test_download_invalid_version(client, version):
    f = (await upload(client)).json()
    r = await client.get(f"/api/files/{f['id']}/download?version={version}")
    assert_error(r, 400, "VALIDATION_ERROR")


@pytest.mark.asyncio
@pytest.mark.parametrize("file_id", [random_uuid(), "not-a-uuid", "1"])
async def test_download_unknown_id(client, file_id):
    assert_error(await client.get(f"/api/files/{file_id}/download"), 404, "NOT_FOUND")


@pytest.mark.asyncio
async def test_download_deleted_file(client, db):
    f = (await upload(client)).json()
    db("UPDATE files SET deleted_at = now() WHERE id = :id", id=f["id"])
    assert_error(await client.get(f"/api/files/{f['id']}/download"), 404, "NOT_FOUND")


# --- detail (cut if late) ----------------------------------------------------


@pytest.mark.asyncio
async def test_detail_returns_file(client):
    uploaded = (await upload(client)).json()
    r = await client.get(f"/api/files/{uploaded['id']}")
    assert r.status_code == 200
    assert r.json() == uploaded


@pytest.mark.asyncio
@pytest.mark.parametrize("file_id", [random_uuid(), "not-a-uuid"])
async def test_detail_unknown_id(client, file_id):
    assert_error(await client.get(f"/api/files/{file_id}"), 404, "NOT_FOUND")


@pytest.mark.asyncio
async def test_detail_deleted_file(client, db):
    f = (await upload(client)).json()
    db("UPDATE files SET deleted_at = now() WHERE id = :id", id=f["id"])
    assert_error(await client.get(f"/api/files/{f['id']}"), 404, "NOT_FOUND")
