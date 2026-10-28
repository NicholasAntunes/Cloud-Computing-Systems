"""Blob operations: naming, upload, download, delete, copy, list."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from .models import Download, UploadResult

CHUNK_SIZE = 4 * 1024 * 1024  # bytes per chunk when streaming (4 MiB)


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

    Raises:
        FileTooLarge: more than ``max_bytes`` were received.
        BlobAlreadyExists: ``name`` is already taken.
    """
    raise NotImplementedError


async def open_download(name: str) -> Download:
    """Open a blob for streaming download.

    Example (FastAPI endpoint)::

        d = await storage.open_download(name)
        return StreamingResponse(d.chunks, media_type=d.content_type,
                                 headers={"Content-Length": str(d.size_bytes), ...})

    Raises:
        BlobNotFound: the blob does not exist.
    """
    raise NotImplementedError


async def delete_blob(name: str) -> None:
    """Delete a blob. Deleting a blob that does not exist is not an error."""
    raise NotImplementedError


async def copy_blob(source: str, target: str) -> None:
    """Copy one blob to a new name in the same container (Phase 5: restore).

    Raises:
        BlobNotFound: ``source`` does not exist.
        BlobAlreadyExists: ``target`` is already taken.
    """
    raise NotImplementedError


async def list_blobs(prefix: str = "") -> list[str]:
    """Return the names of all blobs starting with ``prefix``.

    For debugging and orphan-blob cleanup (Phase 6); the file list shown to users
    comes from the database, not from here.
    """
    raise NotImplementedError
