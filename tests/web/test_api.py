"""The HTTP surface the editor will consume."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from edutap.pass_designer.web.app import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance


DRAFT = {
    "family": "loyalty",
    "head": {
        "issuerName": "Example University",
        "programName": "Library",
        "programLogo": "https://example.org/logo.png",
    },
    "front_rows": [
        {
            "cells": [
                {"first": {"fallback_chain": [{"kind": "text", "module_id": "name"}]}}
            ]
        }
    ],
    "text_modules": [
        {
            "module_id": "name",
            "header": "Name",
            "value": "person.display_name",
            "bound": True,
        }
    ],
}


async def test_families_are_listed_with_their_head_fields(client: AsyncClient) -> None:
    response = await client.get("/designer/v1/families")

    assert response.status_code == 200
    loyalty = next(f for f in response.json() if f["family_id"] == "loyalty")
    assert any(field["key"] == "programName" for field in loyalty["head_fields"])


async def test_personas_are_offered_for_the_preview(client: AsyncClient) -> None:
    response = await client.get("/designer/v1/personas")

    assert response.status_code == 200
    assert {p["gender"] for p in response.json()} >= {"female", "male", "non-binary"}


async def test_validation_reports_an_unresolvable_field_path(
    client: AsyncClient,
) -> None:
    broken = {**DRAFT, "text_modules": []}

    response = await client.post("/designer/v1/validate", json={"draft": broken})

    assert response.status_code == 200
    assert any(f["severity"] == "error" for f in response.json()["findings"])


async def test_export_returns_all_three_artefacts(client: AsyncClient) -> None:
    response = await client.post(
        "/designer/v1/export",
        json={"draft": DRAFT, "class_id": "1.a", "object_id": "1.b"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["class_json"]["id"] == "1.a"
    assert body["object_json"]["textModulesData"][0]["body"] == "${person.display_name}"
    assert body["mappings"]["rules"][0]["source_field"] == "person.display_name"


async def test_export_refuses_a_draft_with_errors(client: AsyncClient) -> None:
    broken = {**DRAFT, "text_modules": []}

    response = await client.post(
        "/designer/v1/export",
        json={"draft": broken, "class_id": "1.a", "object_id": "1.b"},
    )

    assert response.status_code == 422


async def test_import_returns_a_draft(client: AsyncClient) -> None:
    exported = (
        await client.post(
            "/designer/v1/export",
            json={"draft": DRAFT, "class_id": "1.a", "object_id": "1.b"},
        )
    ).json()

    response = await client.post(
        "/designer/v1/import",
        json={
            "family": "loyalty",
            "class_json": exported["class_json"],
            "object_json": exported["object_json"],
        },
    )

    assert response.status_code == 200
    assert response.json()["text_modules"][0]["bound"] is True
