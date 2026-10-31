"""Files: upload, list, detail and download (Phase 1). Versions follow in Phase 5.

Package layout:
    schemas.py  FileOut, UserRef, Permissions, FileList (the File object of docs/API.md)
    service.py  database queries and the upload (blob first, then one transaction)
    router.py   the ``/api/files`` endpoints
"""

from .router import router

__all__ = ["router"]
