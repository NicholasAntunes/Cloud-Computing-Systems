"""Blob operations: naming, upload, download, delete, copy, list."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from uuid import UUID

from azure.core import MatchConditions
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import StorageStreamDownloader

from .client import get_container
from .errors import FileTooLarge, StorageError, translate_azure_errors
from .models import Download, UploadResult

_DEFAULT_CONTENT_TYPE = "application/octet-stream"
_COPY_POLL_SECONDS = 0.2


def blob_name(file_id: UUID, version_no: int) -> str:
    """Return the blob name for one version of a file: ``{file_id}/{version_no}``.

    The user's file name is never part of the blob name.
    """
    if version_no < 1:
        raise ValueError("version_no starts at 1")
    return f"{file_id}/{version_no}"


async def upload_stream(
    name: str,
    chunks: AsyncIterator[bytes],
    content_type: str,
    max_bytes: int,
) -> UploadResult:
    """Stream ``chunks`` into a new blob, computing its size and SHA-256 on the fly.

    The file is never loaded fully into memory. Never overwrites an existing blob.

    Example (FastAPI endpoint)::

        async def chunks():
            while data := await upload.read(storage.CHUNK_SIZE):
                yield data

        result = await storage.upload_stream(
            storage.blob_name(file_id, 1), chunks(), upload.content_type, max_bytes
        )

    The blob is written as blocks and only becomes visible when the block list is
    committed at the end, so a failed upload leaves no blob behind (Azure discards
    uncommitted blocks on its own).

    Raises:
        FileTooLarge: more than ``max_bytes`` were received.
        BlobAlreadyExists: ``name`` is already taken.
    """
    sha256 = hashlib.sha256()
    size = 0

    async def checked_chunks() -> AsyncIterator[bytes]:
        nonlocal size
        async for chunk in chunks:
            size += len(chunk)
            if size > max_bytes:
                raise FileTooLarge(f"upload is larger than {max_bytes} bytes")
            sha256.update(chunk)
            yield chunk

    blob = get_container().get_blob_client(name)
    with translate_azure_errors():
        response = await blob.upload_blob(
            checked_chunks(),
            overwrite=False,
            content_settings=ContentSettings(
                content_type=content_type or _DEFAULT_CONTENT_TYPE
            ),
        )
    return UploadResult(size_bytes=size, sha256=sha256.hexdigest(), etag=response["etag"])


async def open_download(name: str) -> Download:
    """Open a blob for streaming download.

    Example (FastAPI endpoint)::

        d = await storage.open_download(name)
        return StreamingResponse(d.chunks, media_type=d.content_type,
                                 headers={"Content-Length": str(d.size_bytes), ...})

    Raises:
        BlobNotFound: the blob does not exist.
    """
    blob = get_container().get_blob_client(name)
    with translate_azure_errors():
        downloader = await blob.download_blob()
    return Download(
        size_bytes=downloader.size,
        content_type=downloader.properties.content_settings.content_type
        or _DEFAULT_CONTENT_TYPE,
        chunks=_translated_chunks(downloader),
    )


async def _translated_chunks(downloader: StorageStreamDownloader) -> AsyncIterator[bytes]:
    """Yield the downloader's chunks, translating Azure errors raised mid-stream."""
    with translate_azure_errors():
        async for chunk in downloader.chunks():
            yield chunk


async def delete_blob(name: str) -> None:
    """Delete a blob. Deleting a blob that does not exist is not an error."""
    blob = get_container().get_blob_client(name)
    with translate_azure_errors():
        try:
            await blob.delete_blob()
        except ResourceNotFoundError:
            pass


async def copy_blob(source: str, target: str) -> None:
    """Copy one blob to a new name in the same container (Phase 5: restore).

    The copy happens inside Blob Storage; the bytes never pass through the API.
    Returns once the copy has finished.

    Raises:
        BlobNotFound: ``source`` does not exist.
        BlobAlreadyExists: ``target`` is already taken.
    """
    container = get_container()
    source_blob = container.get_blob_client(source)
    target_blob = container.get_blob_client(target)
    with translate_azure_errors():
        # Checked first so a missing source always gives BlobNotFound; the
        # service's own answer for it differs between Azurite and Azure.
        await source_blob.get_blob_properties()
        copy = await target_blob.start_copy_from_url(
            source_blob.url, match_condition=MatchConditions.IfMissing
        )
        status = copy["copy_status"]
        while status == "pending":
            await asyncio.sleep(_COPY_POLL_SECONDS)
            status = (await target_blob.get_blob_properties()).copy.status
    if status != "success":
        raise StorageError(f"copy {source} -> {target} ended with status {status!r}")


async def list_blobs(prefix: str = "") -> list[str]:
    """Return the names of all blobs starting with ``prefix``.

    For debugging and orphan-blob cleanup (Phase 6); the file list shown to users
    comes from the database, not from here.
    """
    with translate_azure_errors():
        return [
            name
            async for name in get_container().list_blob_names(
                name_starts_with=prefix or None
            )
        ]
