"""FastAPI application: ``uvicorn app.main:app``.

Every route starts with ``/api``: Caddy forwards ``/api/*`` to the API without
stripping the prefix (docs/PLAN.md §9), so the docs live under it as well.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db, storage
from app.config import Settings
from app.errors import install_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own ``settings``.

    Without ``settings``, they are read from the environment at startup, not at
    import, so importing this module never needs the environment.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app_settings = settings or Settings()
        await storage.init_storage(app_settings.storage_settings())
        engine = db.create_engine(app_settings)
        app.state.settings = app_settings
        app.state.sessionmaker = db.create_sessionmaker(engine)
        try:
            yield
        finally:
            await engine.dispose()
            await storage.close_storage()

    app = FastAPI(
        title="Cloud File Exchange API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    install_error_handlers(app)

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness check: the API process is up. Doesn't query the database or storage."""
        return {"status": "ok"}

    return app


app = create_app()
