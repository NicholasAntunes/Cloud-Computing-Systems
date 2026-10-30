"""Evidence for slides 3 and 6: Azurite has no Blob versioning and no soft delete.

Runs a few plain Blob Storage operations against Azurite and prints what the
service answers. On an Azure storage account with versioning and soft delete
turned on, overwriting a blob keeps the old content as a previous version and a
deleted blob can be undeleted. On Azurite neither happens, which is why our
version control lives in our own code (docs/PLAN.md §3).

Run from the api/ folder with Azurite listening on 127.0.0.1:10000:

    python scripts/azurite_versioning_check.py

The saved output is in docs/evidence/azurite-versioning.txt. Set
BLOB_CONNECTION_STRING to point at another Azurite. The script uses its own
random container and deletes it at the end.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient, RetentionPolicy
from azure.storage.blob import __version__ as sdk_version

CONNECTION_STRING = os.environ.get("BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
BLOB = "demo.txt"


def error_text(e: AzureError) -> str:
    """First line of an Azure error, without the long request details."""
    return f"{type(e).__name__}: {str(e).splitlines()[0]}"


def main() -> None:
    service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    server: dict[str, str] = {}
    original_properties = service.get_service_properties(
        raw_response_hook=lambda r: server.update(
            name=r.http_response.headers.get("Server", "unknown")
        )
    )

    print("Azurite blob versioning / soft delete check")
    print(f"Date:        {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    print(f"Endpoint:    {service.url}")
    print(f"Server:      {server['name']}")
    print(f"Python SDK:  azure-storage-blob {sdk_version}")

    container = service.create_container(f"evidence-{uuid.uuid4().hex[:12]}")
    blob = container.get_blob_client(BLOB)
    try:
        # 1. Blob versioning -------------------------------------------------
        print("\n1. Blob versioning")
        first = blob.upload_blob(b"version 1", overwrite=False)
        second = blob.upload_blob(b"version 2", overwrite=True)
        print(f"   upload 'version 1' -> version_id = {first.get('version_id')}")
        print(f"   upload 'version 2' -> version_id = {second.get('version_id')}")
        print(f"   download now returns {blob.download_blob().readall()!r}")

        try:
            listed = list(container.list_blobs(include=["versions"]))
            print(f"   list_blobs(include=versions) -> {len(listed)} entry(ies):")
            for item in listed:
                print(f"     {item.name}  version_id={item.version_id}")
            versions_kept = len(listed) > 1 or any(i.version_id for i in listed)
        except AzureError as e:
            print(f"   list_blobs(include=versions) -> {error_text(e)}")
            versions_kept = False

        # 2. Soft delete -----------------------------------------------------
        print("\n2. Soft delete")
        try:
            service.set_service_properties(
                delete_retention_policy=RetentionPolicy(enabled=True, days=7)
            )
            policy = service.get_service_properties()["delete_retention_policy"]
            print(f"   enable 7-day delete retention -> accepted, reads back enabled={policy.enabled}")
        except AzureError as e:
            print(f"   enable 7-day delete retention -> {error_text(e)}")

        blob.delete_blob()
        print("   delete demo.txt -> done")
        try:
            deleted = [b.name for b in container.list_blobs(include=["deleted"]) if b.deleted]
            print(f"   list_blobs(include=deleted) -> deleted blobs: {deleted}")
        except AzureError as e:
            print(f"   list_blobs(include=deleted) -> {error_text(e)}")
        try:
            blob.undelete_blob()
            blob.get_blob_properties()
            print("   undelete demo.txt -> blob is back")
            undeleted = True
        except AzureError as e:
            print(f"   undelete demo.txt -> {error_text(e)}")
            undeleted = False

        # Summary --------------------------------------------------------------
        print("\nResult")
        print(f"   Old content kept after overwrite (versioning): {'yes' if versions_kept else 'NO'}")
        print(f"   Deleted blob can be restored (soft delete):    {'yes' if undeleted else 'NO'}")
        print("   -> Versioning must be implemented in our own code: every version is a")
        print("      new, never-modified blob {file_id}/{version_no} (docs/PLAN.md §3).")
    finally:
        container.delete_container()
        service.set_service_properties(
            delete_retention_policy=original_properties["delete_retention_policy"]
        )


if __name__ == "__main__":
    main()
