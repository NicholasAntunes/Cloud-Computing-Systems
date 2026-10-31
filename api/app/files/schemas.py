"""Response bodies of the file endpoints: the File object of docs/API.md."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, PlainSerializer, WithJsonSchema


def _utc_iso(value: datetime) -> str:
    """``2026-11-02T14:05:31Z``: UTC, whole seconds, ``Z`` (docs/API.md "Dates")."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


UtcDateTime = Annotated[
    datetime,
    PlainSerializer(_utc_iso, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]


class UserRef(BaseModel):
    id: int
    username: str


class Permissions(BaseModel):
    """What the current user may do with this file. Phase 1: everything."""

    can_read: bool
    can_update: bool
    can_share: bool
    can_delete: bool


class FileOut(BaseModel):
    """A file with its current version.

    ``size_bytes``, ``updated_at`` and ``updated_by`` describe the current version
    (``file_versions.size_bytes`` / ``uploaded_at`` / ``uploaded_by``).
    """

    id: uuid.UUID
    name: str
    content_type: str
    size_bytes: int
    current_version: int
    created_at: UtcDateTime
    updated_at: UtcDateTime
    owner: UserRef
    updated_by: UserRef
    permissions: Permissions


class FileList(BaseModel):
    items: list[FileOut]
    total: int
