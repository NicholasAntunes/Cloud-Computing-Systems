"""Shared Blob client: created once at API startup, closed at shutdown."""

from __future__ import annotations

from azure.core.exceptions import ResourceExistsError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient, ContainerClient

from .errors import translate_azure_errors
from .settings import CHUNK_SIZE, StorageSettings

# Set by init_storage, cleared by close_storage.
_service: BlobServiceClient | None = None
_container: ContainerClient | None = None
_credential: DefaultAzureCredential | None = None  # only with managed identity

# Keep every request to one chunk, so no upload or download ever holds more than
# CHUNK_SIZE bytes in memory (the SDK defaults buffer up to 32-64 MiB).
_TRANSFER_SIZES = {
    "max_single_put_size": CHUNK_SIZE,
    "max_block_size": CHUNK_SIZE,
    "max_single_get_size": CHUNK_SIZE,
    "max_chunk_get_size": CHUNK_SIZE,
}


async def init_storage(settings: StorageSettings) -> None:
    """Create the shared Blob client and make sure the container exists.

    Call once at API startup (FastAPI lifespan). ``connection_string`` builds the
    client from the connection string; ``managed_identity`` uses
    ``DefaultAzureCredential``. The rest of the package does not know which one
    is in use.

    Raises:
        ValueError: the setting required by ``settings.auth`` is missing.
        RuntimeError: storage is already initialised.
        StorageError: Blob Storage cannot be reached.
    """
    global _service, _container, _credential
    if _service is not None:
        raise RuntimeError("storage is already initialised")

    credential = None
    if settings.auth == "connection_string":
        if not settings.connection_string:
            raise ValueError(
                "BLOB_CONNECTION_STRING is required when STORAGE_AUTH=connection_string"
            )
        service = BlobServiceClient.from_connection_string(
            settings.connection_string, **_TRANSFER_SIZES
        )
    elif settings.auth == "managed_identity":
        if not settings.account_url:
            raise ValueError(
                "BLOB_ACCOUNT_URL is required when STORAGE_AUTH=managed_identity"
            )
        credential = DefaultAzureCredential()
        service = BlobServiceClient(
            settings.account_url, credential=credential, **_TRANSFER_SIZES
        )
    else:
        raise ValueError(f"unknown STORAGE_AUTH {settings.auth!r}")

    container = service.get_container_client(settings.container)
    try:
        with translate_azure_errors():
            try:
                await container.create_container()
            except ResourceExistsError:
                pass
    except BaseException:
        await service.close()
        if credential is not None:
            await credential.close()
        raise

    _service, _container, _credential = service, container, credential


async def close_storage() -> None:
    """Close the shared Blob client. Call once at API shutdown. Safe to call twice."""
    global _service, _container, _credential
    if _service is not None:
        await _service.close()
    if _credential is not None:
        await _credential.close()
    _service = _container = _credential = None


def get_container() -> ContainerClient:
    """Return the shared container client for the blob operations.

    Internal to the package; not re-exported.

    Raises:
        RuntimeError: ``init_storage`` has not been called.
    """
    if _container is None:
        raise RuntimeError("storage is not initialised; call init_storage() first")
    return _container
