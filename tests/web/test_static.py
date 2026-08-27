"""The single-page app is served by the same application as the API."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from edutap.pass_designer.web import app as app_module
from edutap.pass_designer.web.app import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _build_static(tmp_path: Path) -> Path:
    """Arrange a minimal built SPA: `index.html` plus an empty `assets/`.

    `StaticFiles` requires its directory to exist at mount time, so the
    catch-all route this test depends on is only registered when both are
    present — exactly what a real `pnpm build` output looks like, and not
    something either test may assume is already sitting on the developer's
    (or CI's) filesystem.
    """
    static_dir = tmp_path / "static"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return static_dir


async def test_the_api_still_answers_when_no_build_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A developer who has never run `make build-frontend` must still be able to
    # run the tests and the API. A missing build is not an error. Pointed at an
    # empty tmp_path rather than relying on this checkout's own (gitignored)
    # `static/` being absent — CI never builds the frontend before
    # `make test-local`, but a developer's checkout might have run
    # `make build-frontend` earlier, and the test must not depend on that.
    monkeypatch.setattr(app_module, "STATIC_DIR", tmp_path / "static")

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/designer/v1/families")

    assert response.status_code == 200


async def test_an_unknown_path_does_not_shadow_the_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The catch-all is only registered when a build exists, so this test must
    # arrange one itself rather than hoping the checkout happens to have run
    # `make build-frontend` — otherwise the catch-all is simply absent, an
    # unrelated FastAPI 404 fires for an unrelated reason, and the test passes
    # whether or not the guard in `app.py` is even there.
    monkeypatch.setattr(app_module, "STATIC_DIR", _build_static(tmp_path))

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/designer/v1/nonesuch")

    # Still a 404 from the router, never the SPA's index.html: an API path that
    # silently returns HTML is the failure mode that wastes an afternoon.
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")
