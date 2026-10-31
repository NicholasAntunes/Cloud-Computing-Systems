"""File logic behind ``router.py``: database queries and the upload.

Every File returned joins its current version, owner and uploader. Deleted files
(``deleted_at`` set) are invisible everywhere. Phase 2 adds the READ filter to
``_files_query`` and ``find_version``; the endpoints don't change.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from starlette.datastructures import UploadFile

from app import storage
from app.errors import ApiError
from app.models import File, FileVersion, User

from .schemas import FileList, FileOut, Permissions, UserRef

logger = logging.getLogger(__name__)

_DEFAULT_CONTENT_TYPE = "application/octet-stream"

# Phase 1 has no rights yet: the admin may do everything.
_ALL_RIGHTS = Permissions(can_read=True, can_update=True, can_share=True, can_delete=True)

_Owner = aliased(User, name="owner")
_Uploader = aliased(User, name="uploader")


def _files_query() -> Select:
    """Visible files as ``(File, current FileVersion, owner User, uploader User)`` rows."""
    return (
        select(File, FileVersion, _Owner, _Uploader)
        .join(
            FileVersion,
            (FileVersion.file_id == File.id) & (FileVersion.version_no == File.current_version),
        )
        .join(_Owner, _Owner.id == File.owner_id)
        .join(_Uploader, _Uploader.id == FileVersion.uploaded_by)
        .where(File.deleted_at.is_(None))
    )


def _file_out(file: File, version: FileVersion, owner: User, uploader: User) -> FileOut:
    return FileOut(
        id=file.id,
        name=file.name,
        content_type=file.content_type,
        size_bytes=version.size_bytes,
        current_version=file.current_version,
        created_at=file.created_at,
        updated_at=version.uploaded_at,
        owner=UserRef(id=owner.id, username=owner.username),
        updated_by=UserRef(id=uploader.id, username=uploader.username),
        permissions=_ALL_RIGHTS,
    )


async def list_files(session: AsyncSession, limit: int, offset: int) -> FileList:
    """One page of files, newest ``updated_at`` first, and the total count."""
    query = _files_query()
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    # FileVersion.id breaks ties between uploads in the same microsecond.
    page = query.order_by(FileVersion.uploaded_at.desc(), FileVersion.id.desc())
    rows = await session.execute(page.limit(limit).offset(offset))
    return FileList(items=[_file_out(*row) for row in rows], total=total or 0)


async def get_file(session: AsyncSession, file_id: uuid.UUID) -> FileOut:
    """The file ``file_id``.

    Raises:
        ApiError: 404 ``NOT_FOUND`` if it doesn't exist or is deleted.
    """
    row = (await session.execute(_files_query().where(File.id == file_id))).one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "File not found.")
    return _file_out(*row)


async def find_version(
    session: AsyncSession, file_id: uuid.UUID, version_no: int | None
) -> tuple[File, FileVersion]:
    """The file and its version ``version_no``, or its current version if ``None``.

    Raises:
        ApiError: 404 ``NOT_FOUND`` if the file doesn't exist, is deleted or has no
            such version.
    """
    wanted = File.current_version if version_no is None else version_no
    row = (
        await session.execute(
            select(File, FileVersion)
            .join(FileVersion, FileVersion.file_id == File.id)
            .where(File.id == file_id, File.deleted_at.is_(None), FileVersion.version_no == wanted)
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "File or version not found.")
    return row.File, row.FileVersion


def _content_type(declared: str | None) -> str:
    """The type the client declared if it is a plausible header value, else the default.

    Only a label: downloads are always attachments with ``nosniff``, so a wrong or
    hostile type can't make the browser render or run the file.
    """
    if declared and len(declared) <= 255 and declared.isascii() and declared.isprintable():
        return declared
    return _DEFAULT_CONTENT_TYPE


async def create_file(
    session: AsyncSession, user: User, upload: UploadFile, max_bytes: int
) -> FileOut:
    """Store ``upload`` as a new file with version 1 and return it.

    The blob is streamed first, under a new UUID (never the user's file name);
    then ``files`` and ``file_versions`` are inserted in one transaction. If the
    database step fails, the blob is deleted again, so no file is left half
    stored. ``upload.filename`` must already be checked (non-empty, ≤ 255 chars).

    Raises:
        storage.FileTooLarge: more than ``max_bytes`` were received; nothing stored.
        storage.StorageError: Blob Storage failed; nothing stored.
        sqlalchemy.exc.SQLAlchemyError: the database step failed; the blob was deleted.
    """
    file_id = uuid.uuid4()
    blob = storage.blob_name(file_id, 1)
    content_type = _content_type(upload.content_type)

    async def chunks() -> AsyncIterator[bytes]:
        while data := await upload.read(storage.CHUNK_SIZE):
            yield data

    result = await storage.upload_stream(blob, chunks(), content_type, max_bytes)
    try:
        async with session.begin():
            session.add(
                File(
                    id=file_id,
                    owner_id=user.id,
                    name=upload.filename,
                    content_type=content_type,
                    current_version=1,
                )
            )
            session.add(
                FileVersion(
                    file_id=file_id,
                    version_no=1,
                    blob_name=blob,
                    size_bytes=result.size_bytes,
                    sha256=result.sha256,
                    uploaded_by=user.id,
                )
            )
            # Read back with the detail query (this flushes the inserts), so upload,
            # list and detail always return the same File.
            return await get_file(session, file_id)
    except Exception:
        await _delete_blob_quietly(blob)
        raise


async def _delete_blob_quietly(name: str) -> None:
    """Delete the blob of a failed upload; log, don't raise, if that fails too.

    The client should get the original error. A blob left behind has no row, so
    nobody can reach it; Phase 6 cleanup removes such orphans.
    """
    try:
        await storage.delete_blob(name)
    except storage.StorageError:
        logger.exception("Could not delete blob %s after a failed upload", name)
