"""The single-page app is served by the same application as the API."""

import pytest
from httpx import ASGITransport, AsyncClient

from edutap.pass_designer.web.app import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_the_api_still_answers_when_no_build_exists() -> None:
    # A developer who has never run `make build-frontend` must still be able to
    # run the tests and the API. A missing build is not an error.
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/designer/v1/families")

    assert response.status_code == 200


async def test_an_unknown_path_does_not_shadow_the_api() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/designer/v1/nonesuch")

    # Still a 404 from the router, never the SPA's index.html: an API path that
    # silently returns HTML is the failure mode that wastes an afternoon.
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")
