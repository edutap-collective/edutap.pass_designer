"""The FastAPI application."""

from fastapi import FastAPI

from ..settings import get_settings
from .routers import design


def create_app() -> FastAPI:
    """Return a configured application instance."""
    settings = get_settings()
    app = FastAPI(
        title="eduTAP Pass Designer",
        version="0.1.0",
        root_path=settings.root_path,
    )
    app.include_router(design.router)
    return app


# Read at import time so `uvicorn edutap.pass_designer.web.app:app` (the
# Dockerfile's CMD, and the "without a container" instructions) has an ASGI
# app to load without another entry point. Tests do not use this instance —
# they call `create_app()` themselves (see `tests/web/test_api.py`), each
# getting a fresh `FastAPI` built from the settings in effect at that moment,
# so this module-level call reading settings once at import time does not
# leak stale configuration into them.
app = create_app()
