"""API settings, read from environment variables (docs/PLAN.md §9).

This is the only module that reads the environment. Field names are the variable
names in lower case (``DATABASE_URL`` → ``database_url``). Outside Docker, values
can also come from ``api/.env`` (see ``api/.env.example``); real environment
variables win over the file.

Secrets (``JWT_SECRET``, ``ADMIN_PASSWORD``) are ``SecretStr``, so they never show
up in logs or tracebacks; read them with ``.get_secret_value()``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.storage import StorageSettings


class Settings(BaseSettings):
    """All settings of the API. Missing required values fail at startup.

    Raises:
        pydantic.ValidationError: a required variable is missing or invalid.
    """

    # extra="ignore": the Compose .env also holds variables for other services.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Blob Storage
    storage_auth: Literal["connection_string", "managed_identity"]
    blob_connection_string: str | None = None  # with STORAGE_AUTH=connection_string
    blob_account_url: str | None = None  # with STORAGE_AUTH=managed_identity
    blob_container: str = "files"

    # Database, e.g. postgresql+psycopg://user:password@db:5432/cloudfiles
    database_url: str

    # Tokens (Phase 2)
    jwt_secret: SecretStr
    access_token_minutes: int = Field(default=15, gt=0)
    refresh_token_days: int = Field(default=7, gt=0)

    # Uploads
    max_upload_mb: int = Field(default=100, gt=0)

    # Comma-separated origins. Unused while the web app and the API share one origin
    # behind Caddy (docs/API.md); CORS is configured in Phase 6.
    cors_origins: str = ""

    # First admin, created at startup when the users table is empty.
    admin_username: str = "admin"
    admin_email: str
    admin_password: SecretStr

    @property
    def max_upload_bytes(self) -> int:
        """``MAX_UPLOAD_MB`` in bytes (1 MB = 1024 × 1024 bytes)."""
        return self.max_upload_mb * 1024 * 1024

    def storage_settings(self) -> StorageSettings:
        """The settings for ``storage.init_storage``."""
        return StorageSettings(
            auth=self.storage_auth,
            container=self.blob_container,
            connection_string=self.blob_connection_string,
            account_url=self.blob_account_url,
        )
