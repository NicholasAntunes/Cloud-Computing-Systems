"""Blob Storage access for the Cloud File Exchange API.

This package is the only code that talks to Blob Storage (Azurite locally, Azure
in the cloud). It knows nothing about users, rights or the database: the API
endpoints check rights, write the database rows and turn the exceptions below
into HTTP responses.

Blob layout: one private container (``files`` by default) with one blob per file
version, named ``{file_id}/{version_no}``. Blobs are never overwritten: a new
version is always a new blob. See docs/PLAN.md §3 and §6.

Everything public is re-exported here, so callers only ever write::

    from app import storage
    await storage.upload_stream(...)

Package layout:
    settings.py  StorageSettings
    models.py    UploadResult, Download
    errors.py    StorageError and its subclasses
    client.py    init_storage, close_storage (shared Blob client)
    blobs.py     blob operations

Status: interface only. Every function except ``blob_name`` raises
``NotImplementedError`` until it is implemented.
"""

from .blobs import (
    CHUNK_SIZE,
    blob_name,
    copy_blob,
    delete_blob,
    list_blobs,
    open_download,
    upload_stream,
)
from .client import close_storage, init_storage
from .errors import BlobAlreadyExists, BlobNotFound, FileTooLarge, StorageError
from .models import Download, UploadResult
from .settings import StorageSettings

__all__ = [
    # Configuration and lifecycle
    "StorageSettings",
    "init_storage",
    "close_storage",
    # Blob operations
    "CHUNK_SIZE",
    "blob_name",
    "upload_stream",
    "open_download",
    "delete_blob",
    "copy_blob",
    "list_blobs",
    # Results
    "UploadResult",
    "Download",
    # Errors
    "StorageError",
    "FileTooLarge",
    "BlobNotFound",
    "BlobAlreadyExists",
]
