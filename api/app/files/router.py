"""The ``/api/files`` endpoints of Phase 1: upload, list, detail, download (docs/API.md).

Every endpoint depends on ``current_user`` (router-level), so Phase 2 only has to
change that dependency to require a valid token.
"""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import FormData, UploadFile

from app import storage
from app.auth import current_user
from app.db import get_session
from app.errors import ApiError
from app.models import User

from . import service
from .schemas import FileList, FileOut

DbSession = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]

router = APIRouter(prefix="/api/files", tags=["files"], dependencies=[Depends(current_user)])

# Room for the multipart framing around the file (boundary, part headers).
_MULTIPART_SLACK = 1024 * 1024

# The upload reads its form itself (see upload_file), so FastAPI can't derive the
# request body from the signature; this gives Swagger UI its file picker.
_UPLOAD_FORM = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {"type": "string", "contentMediaType": "application/octet-stream"}
                    },
                }
            }
        },
    }
}


@router.post("", status_code=201, openapi_extra=_UPLOAD_FORM)
async def upload_file(request: Request, user: CurrentUser, session: DbSession) -> FileOut:
    """Upload a new file as version 1: ``multipart/form-data`` with one field ``file``."""
    # The form is parsed here instead of declaring an ``UploadFile`` parameter,
    # because FastAPI reads such a body to disk before any dependency or check
    # runs. This way ``current_user`` (the token check in Phase 2) and the
    # Content-Length check reject a request before its body is read.
    max_bytes = request.app.state.settings.max_upload_bytes
    _check_content_length(request, max_bytes)
    async with request.form(max_files=1) as form:
        upload = _uploaded_file(form)
        return await service.create_file(session, user, upload, max_bytes)


@router.get("")
async def list_files(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FileList:
    """Files the user may read, newest ``updated_at`` first."""
    return await service.list_files(session, limit, offset)


@router.get("/{file_id}")
async def get_file(file_id: uuid.UUID, session: DbSession) -> FileOut:
    """One file. 404 for an unknown, deleted or malformed ID."""
    return await service.get_file(session, file_id)


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    session: DbSession,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> StreamingResponse:
    """The file's bytes, streamed from Blob Storage: ``version``, or the current one.

    Always an attachment with ``nosniff``: the browser saves the file and never
    renders it, so an uploaded HTML or SVG file can't run script on our origin.
    """
    # Ending the transaction returns the database connection to the pool before
    # the (possibly long) stream starts.
    async with session.begin():
        file, file_version = await service.find_version(session, file_id, version)
    download = await storage.open_download(file_version.blob_name)
    headers = {
        # Set directly rather than as media_type, so Starlette adds no charset.
        "Content-Type": download.content_type,
        "Content-Length": str(download.size_bytes),
        "Content-Disposition": _attachment(file.name),
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(download.chunks, headers=headers)


def _check_content_length(request: Request, max_bytes: int) -> None:
    """Reject a body that declares itself far over the limit, before reading it.

    Stops honest clients (browsers always send Content-Length) early. It is not the
    real limit: the header can be missing (chunked upload) or the multipart slack
    can hide a few bytes; ``upload_stream``'s ``max_bytes`` is.

    Raises:
        storage.FileTooLarge: answered as 413 ``FILE_TOO_LARGE``, like the real limit.
    """
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > max_bytes + _MULTIPART_SLACK:
        raise storage.FileTooLarge(f"Content-Length {length} is over the upload limit")


def _uploaded_file(form: FormData) -> UploadFile:
    """The ``file`` field of the form.

    Raises:
        ApiError: 400 ``VALIDATION_ERROR`` if it is missing or not a file, the file
            is empty, or its name is empty or longer than ``files.name`` allows.
    """
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise _invalid_file("A file is required in the form field 'file'.")
    if not upload.size:
        raise _invalid_file("The file is empty.")
    if not upload.filename or len(upload.filename) > 255:
        raise _invalid_file("The file name must be 1 to 255 characters long.")
    return upload


def _invalid_file(message: str) -> ApiError:
    return ApiError(400, "VALIDATION_ERROR", message, [{"field": "file", "message": message}])


def _attachment(name: str) -> str:
    """``Content-Disposition`` that makes the browser download the file as ``name``.

    ``filename*`` carries the real name, UTF-8 and percent-encoded (RFC 6266,
    RFC 8187). ``filename`` is an ASCII fallback for old clients: anything outside
    printable ASCII, and ``"`` or ``\\``, becomes ``_``. Neither form can contain
    CR/LF or quotes, so a file name can't break or inject headers.
    """
    fallback = "".join(c if " " <= c <= "~" and c not in '"\\' else "_" for c in name)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"
