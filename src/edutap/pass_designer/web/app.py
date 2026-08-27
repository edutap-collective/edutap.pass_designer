"""The FastAPI application."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

    # The built SPA, if there is one. Mounted last and under a catch-all so
    # the API keeps its paths: `/designer/v1/...` is matched by the router
    # above and never reaches this.
    static_dir = Path(__file__).parent / "static"
    if (static_dir / "index.html").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=static_dir / "assets"),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> FileResponse:
            """Serve the single-page app for any path the API does not claim.

            A single-page app owns its own routing, so a deep link has to
            return index.html rather than a 404 — the browser then resolves
            the route client-side.

            FastAPI matches routes in registration order: `/designer/v1/...`
            is claimed by the router above, so only paths the API does not
            recognize reach this handler. That includes unknown API paths
            like `/designer/v1/nonesuch`, which never registered a route of
            its own — without the check below this handler would answer with
            `200 text/html` instead of the router's `404`, and a client that
            expects JSON would silently parse a page.
            """
            if full_path.startswith(design.router.prefix.lstrip("/")):
                raise HTTPException(status_code=404)
            return FileResponse(static_dir / "index.html")

    return app


# Read at import time so `uvicorn edutap.pass_designer.web.app:app` (the
# Dockerfile's CMD, and the "without a container" instructions) has an ASGI
# app to load without another entry point. Tests do not use this instance —
# they call `create_app()` themselves (see `tests/web/test_api.py`), each
# getting a fresh `FastAPI` built from the settings in effect at that moment,
# so this module-level call reading settings once at import time does not
# leak stale configuration into them.
app = create_app()
