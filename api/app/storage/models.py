"""Values returned by the blob operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class UploadResult:
    size_bytes: int
    sha256: str  # lowercase hex digest of the stored bytes
    etag: str


@dataclass(frozen=True)
class Download:
    """An open download. Pass ``chunks`` straight to a ``StreamingResponse``."""

    size_bytes: int
    content_type: str
    chunks: AsyncIterator[bytes]
