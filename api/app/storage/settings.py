"""Storage configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CHUNK_SIZE = 4 * 1024 * 1024  # bytes per chunk when streaming (4 MiB)


@dataclass(frozen=True)
class StorageSettings:
    """Storage configuration, built by app/config.py from the environment (PLAN §9).

    Locally (Azurite):  auth="connection_string" and connection_string set.
    On Azure:           auth="managed_identity" and account_url set.
    """

    auth: Literal["connection_string", "managed_identity"]  # STORAGE_AUTH
    container: str = "files"  # BLOB_CONTAINER
    connection_string: str | None = None  # BLOB_CONNECTION_STRING
    account_url: str | None = None  # BLOB_ACCOUNT_URL
