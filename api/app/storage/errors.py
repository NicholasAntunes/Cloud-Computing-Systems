"""Errors raised by the storage package.

No Azure SDK exception ever leaves the package: ``translate_azure_errors`` turns
them into the errors below, so callers never import anything from Azure.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


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
    any other ``AzureError``  → ``StorageError``.

    Internal to the package; not re-exported.
    """
    raise NotImplementedError
