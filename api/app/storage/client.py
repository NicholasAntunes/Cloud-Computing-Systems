"""Shared Blob client: created once at API startup, closed at shutdown."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .settings import StorageSettings

if TYPE_CHECKING:
    from azure.identity.aio import DefaultAzureCredential
    from azure.storage.blob.aio import BlobServiceClient, ContainerClient

# Set by init_storage, cleared by close_storage.
_service: BlobServiceClient | None = None
_container: ContainerClient | None = None
_credential: DefaultAzureCredential | None = None  # only with managed identity


async def init_storage(settings: StorageSettings) -> None:
    """Create the shared Blob client and make sure the container exists.

    Call once at API startup (FastAPI lifespan). ``connection_string`` builds the
    client from the connection string; ``managed_identity`` uses
    ``DefaultAzureCredential``. The rest of the package does not know which one
    is in use.

    Raises:
        ValueError: the setting required by ``settings.auth`` is missing.
    """
    raise NotImplementedError


async def close_storage() -> None:
    """Close the shared Blob client. Call once at API shutdown."""
    raise NotImplementedError


def get_container() -> ContainerClient:
    """Return the shared container client for the blob operations.

    Internal to the package; not re-exported.

    Raises:
        RuntimeError: ``init_storage`` has not been called.
    """
    raise NotImplementedError
