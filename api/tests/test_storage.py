"""Integration tests for app.storage against a real Azurite (no mocks).

Install once from the api/ folder with ``pip install -e ".[dev]"``, then run with
Azurite listening on 127.0.0.1:10000:

    python -m pytest

Set BLOB_CONNECTION_STRING to test against another Azurite (e.g. host ``azurite``
inside Docker Compose). Each test gets its own random container, deleted at the end.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from app import storage
from app.storage.client import get_container

CONNECTION_STRING = os.environ.get("BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")


@pytest_asyncio.fixture
async def container() -> AsyncIterator[str]:
    name = f"test-{uuid.uuid4().hex[:12]}"
    await storage.init_storage(
        storage.StorageSettings(
            auth="connection_string", connection_string=CONNECTION_STRING, container=name
        )
    )
    try:
        yield name
    finally:
        await get_container().delete_container()
        await storage.close_storage()


async def chunks_of(data: bytes, size: int = 64 * 1024) -> AsyncIterator[bytes]:
    for i in range(0, len(data), size):
        yield data[i : i + size]


async def upload(name: str, data: bytes, max_bytes: int = 100 * 1024 * 1024):
    return await storage.upload_stream(name, chunks_of(data), "image/jpeg", max_bytes)


async def download(name: str) -> bytes:
    d = await storage.open_download(name)
    return b"".join([chunk async for chunk in d.chunks])


# --- blob_name (no Azurite needed) ------------------------------------------


def test_blob_name_is_file_id_and_version():
    file_id = uuid.UUID(int=1)
    assert storage.blob_name(file_id, 3) == f"{file_id}/3"


def test_blob_name_rejects_version_zero():
    with pytest.raises(ValueError):
        storage.blob_name(uuid.uuid4(), 0)


# --- lifecycle ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_requires_connection_string():
    with pytest.raises(ValueError):
        await storage.init_storage(storage.StorageSettings(auth="connection_string"))


@pytest.mark.asyncio
async def test_init_requires_account_url_for_managed_identity():
    with pytest.raises(ValueError):
        await storage.init_storage(storage.StorageSettings(auth="managed_identity"))


@pytest.mark.asyncio
async def test_operations_before_init_raise():
    with pytest.raises(RuntimeError):
        await storage.list_blobs()


# --- upload / download -------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_then_download_returns_identical_bytes(container):
    data = os.urandom(10 * 1024 * 1024 + 123)  # several 4 MiB blocks, uneven end

    result = await upload("f/1", data)

    assert result.size_bytes == len(data)
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.etag
    downloaded = await download("f/1")
    assert hashlib.sha256(downloaded).hexdigest() == result.sha256


@pytest.mark.asyncio
async def test_download_reports_size_and_content_type(container):
    await upload("f/1", b"hello")

    d = await storage.open_download("f/1")

    assert d.size_bytes == 5
    assert d.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_empty_file_round_trips(container):
    result = await upload("f/1", b"")

    assert result.size_bytes == 0
    assert result.sha256 == hashlib.sha256(b"").hexdigest()
    assert await download("f/1") == b""


@pytest.mark.asyncio
async def test_upload_over_limit_raises_and_stores_nothing(container):
    with pytest.raises(storage.FileTooLarge):
        await upload("f/1", os.urandom(1024 * 1024), max_bytes=500 * 1024)

    assert await storage.list_blobs() == []


@pytest.mark.asyncio
async def test_upload_exactly_at_limit_is_accepted(container):
    result = await upload("f/1", b"x" * 1000, max_bytes=1000)

    assert result.size_bytes == 1000


@pytest.mark.asyncio
async def test_upload_never_overwrites(container):
    await upload("f/1", b"first")

    with pytest.raises(storage.BlobAlreadyExists):
        await upload("f/1", b"second")

    assert await download("f/1") == b"first"


@pytest.mark.asyncio
async def test_parallel_uploads_to_same_name_only_one_wins(container):
    a, b = os.urandom(5 * 1024 * 1024), os.urandom(5 * 1024 * 1024)

    results = await asyncio.gather(upload("f/1", a), upload("f/1", b), return_exceptions=True)

    winners = [r for r in results if isinstance(r, storage.UploadResult)]
    losers = [r for r in results if isinstance(r, storage.BlobAlreadyExists)]
    assert len(winners) == 1 and len(losers) == 1
    stored = hashlib.sha256(await download("f/1")).hexdigest()
    assert stored == winners[0].sha256


@pytest.mark.asyncio
async def test_download_missing_blob_raises(container):
    with pytest.raises(storage.BlobNotFound):
        await storage.open_download("missing/1")


# --- delete / list / copy ----------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes_blob_and_is_idempotent(container):
    await upload("f/1", b"data")

    await storage.delete_blob("f/1")
    await storage.delete_blob("f/1")

    assert await storage.list_blobs() == []


@pytest.mark.asyncio
async def test_list_blobs_filters_by_prefix(container):
    for name in ("a/1", "a/2", "b/1"):
        await upload(name, b"data")

    assert sorted(await storage.list_blobs("a/")) == ["a/1", "a/2"]
    assert sorted(await storage.list_blobs()) == ["a/1", "a/2", "b/1"]


@pytest.mark.asyncio
async def test_copy_blob_copies_bytes(container):
    data = os.urandom(6 * 1024 * 1024)
    await upload("f/1", data)

    await storage.copy_blob("f/1", "f/2")

    assert await download("f/2") == data
    assert (await storage.open_download("f/2")).content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_copy_blob_never_overwrites_target(container):
    await upload("f/1", b"old")
    await upload("f/2", b"new")

    with pytest.raises(storage.BlobAlreadyExists):
        await storage.copy_blob("f/1", "f/2")

    assert await download("f/2") == b"new"


@pytest.mark.asyncio
async def test_copy_missing_source_raises(container):
    with pytest.raises(storage.BlobNotFound):
        await storage.copy_blob("missing/1", "f/2")
