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


def _resolve(schema: dict, node: dict) -> dict:
    """Follow one `$ref` into `schema["components"]["schemas"]`, if present."""
    if "$ref" in node:
        name = node["$ref"].rsplit("/", maxsplit=1)[-1]
        return schema["components"]["schemas"][name]
    return node


async def test_openapi_documents_the_export_findings_and_scoped_head_fields(
    client: AsyncClient,
) -> None:
    """Guard against the OpenAPI schema drifting back to generic shapes.

    A React client generated from `/openapi.json` needs the *real* error
    shape for `/export`'s `422` (a list of findings, not FastAPI's generic
    `HTTPValidationError`) and the *real* field shape for `/families` (named
    properties, `scope` included) — not `dict[str, Any]` for either.
    """
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    export_422 = schema["paths"]["/designer/v1/export"]["post"]["responses"]["422"]
    export_error_schema = _resolve(
        schema, export_422["content"]["application/json"]["schema"]
    )
    findings_schema = _resolve(schema, export_error_schema["properties"]["detail"])
    finding_item_schema = _resolve(schema, findings_schema["items"])
    assert set(finding_item_schema["properties"]) >= {"severity", "message", "location"}

    families_200 = schema["paths"]["/designer/v1/families"]["get"]["responses"]["200"]
    families_schema = _resolve(
        schema, families_200["content"]["application/json"]["schema"]
    )
    family_item_schema = _resolve(schema, families_schema["items"])
    head_fields_schema = _resolve(
        schema, family_item_schema["properties"]["head_fields"]
    )
    head_field_item_schema = _resolve(schema, head_fields_schema["items"])
    assert "scope" in head_field_item_schema["properties"]
