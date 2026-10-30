"""API errors and the exception handlers that turn them into responses.

Every error response has the body of docs/API.md "Errors"::

    {"error": {"code": "NOT_FOUND", "message": "...", "details": null}}

``message`` is always written here or by the code that raises ``ApiError``, never
taken from an exception: internal details (storage, database, stack traces) only
go to the log.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import storage

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An error with its HTTP status and API.md error code, e.g.
    ``ApiError(404, "NOT_FOUND", "File not found.")``.

    ``message`` is shown to users. ``details`` is only used by ``VALIDATION_ERROR``.
    """

    def __init__(
        self, status: int, code: str, message: str, details: list[dict[str, str]] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def error_response(
    status: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """A response with the API.md error body."""
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(body, status_code=status, headers=headers)


# Errors raised by FastAPI/Starlette themselves (routing, request parsing).
_HTTP_ERRORS = {
    400: ("VALIDATION_ERROR", "The request could not be read."),
    404: ("NOT_FOUND", "Not found."),
    405: ("METHOD_NOT_ALLOWED", "This method is not allowed here."),
}

# Where the request part sits in a validation error location: ("query", "limit").
_LOCATIONS = {"path", "query", "header", "cookie", "body"}


async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message, exc.details)


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        loc = list(err["loc"])
        if len(loc) > 1 and loc[0] in _LOCATIONS:
            loc = loc[1:]
        details.append({"field": ".".join(str(part) for part in loc), "message": err["msg"]})
    return error_response(400, "VALIDATION_ERROR", "Some input is missing or invalid.", details)


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code not in _HTTP_ERRORS:
        # Our own code raises ApiError, so this is a bug: answer like any other one.
        logger.error("Unmapped HTTPException %s on %s", exc.status_code, request.url.path)
        return error_response(500, "INTERNAL_ERROR", "Something went wrong.")
    code, message = _HTTP_ERRORS[exc.status_code]
    details = None
    if code == "VALIDATION_ERROR":
        details = [{"field": "body", "message": message}]
    # Keep headers such as Allow (405).
    return error_response(exc.status_code, code, message, details, headers=exc.headers)


async def _file_too_large(request: Request, exc: storage.FileTooLarge) -> JSONResponse:
    limit = request.app.state.settings.max_upload_mb
    return error_response(413, "FILE_TOO_LARGE", f"The file is larger than the {limit} MB limit.")


async def _blob_not_found(request: Request, exc: storage.BlobNotFound) -> JSONResponse:
    # The database pointed to a blob that isn't there: worth a look in the log.
    logger.warning("Blob not found on %s: %s", request.url.path, exc)
    return error_response(404, "NOT_FOUND", "Not found.")


async def _storage_error(request: Request, exc: storage.StorageError) -> JSONResponse:
    logger.error("Storage error on %s", request.url.path, exc_info=exc)
    return error_response(
        503, "STORAGE_UNAVAILABLE", "File storage is unavailable. Please try again later."
    )


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(500, "INTERNAL_ERROR", "Something went wrong.")


def install_error_handlers(app: FastAPI) -> None:
    """Register every handler above on ``app``.

    Starlette picks the handler of the most specific class, so ``FileTooLarge``
    and ``BlobNotFound`` win over ``StorageError``. The ``Exception`` handler runs
    outermost; Starlette re-raises afterwards, so the server logs it as well.
    """
    handlers: dict[type[Exception], Any] = {
        ApiError: _api_error,
        RequestValidationError: _validation_error,
        StarletteHTTPException: _http_error,
        storage.FileTooLarge: _file_too_large,
        storage.BlobNotFound: _blob_not_found,
        storage.StorageError: _storage_error,
        Exception: _unexpected_error,
    }
    for exc_class, handler in handlers.items():
        app.add_exception_handler(exc_class, handler)
