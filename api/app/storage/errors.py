"""Errors raised by the storage package.

No Azure SDK exception ever leaves the package: ``translate_azure_errors`` turns
them into the errors below, so callers never import anything from Azure.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from azure.core.exceptions import (
    AzureError,
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)


class StorageError(Exception):
    """Base class for all errors raised by the storage package."""


class FileTooLarge(StorageError):
    """The upload exceeded ``max_bytes``. Nothing was stored.

    API maps it to 413 Payload Too Large.
    """


class BlobNotFound(StorageError):
    """The blob does not exist. API maps it to 404 Not Found."""


class BlobAlreadyExists(StorageError):
    """A blob with this name already exists (e.g. two parallel uploads chose the
    same version number). Nothing was written. The caller retries with the next
    version number.
    """


@contextmanager
def translate_azure_errors() -> Iterator[None]:
    """Turn Azure SDK exceptions raised inside the ``with`` block into ours.

    ``ResourceNotFoundError`` → ``BlobNotFound``,
    ``ResourceExistsError``   → ``BlobAlreadyExists``,
    ``ResourceModifiedError`` → ``BlobAlreadyExists`` (the only conditions this
    package sends are "the target must not exist yet"),
    any other ``AzureError``  → ``StorageError``.

    The original Azure exception stays attached as ``__cause__`` for logging.
    Internal to the package; not re-exported.
    """
    try:
        yield
    except ResourceNotFoundError as e:
        raise BlobNotFound(e.message) from e
    except (ResourceExistsError, ResourceModifiedError) as e:
        raise BlobAlreadyExists(e.message) from e
    except AzureError as e:
        raise StorageError(e.message) from e
