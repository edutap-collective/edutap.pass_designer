"""The routes the editor consumes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...draft.models import Draft
from ...exporter.class_json import build_class
from ...exporter.mappings import build_mappings
from ...exporter.object_json import build_object
from ...importer.reader import read
from ...personas.catalogue import catalogue_types, load_catalogue
from ...personas.generator import Persona, build_personas
from ...platforms.google import families
from ...settings import Settings, get_settings
from ...validation import Finding, validate

router = APIRouter(prefix="/designer/v1", tags=["designer"])


class ValidateRequest(BaseModel):
    """Body of `POST /validate`."""

    draft: Draft


class ValidateResponse(BaseModel):
    """Body of the `/validate` response."""

    findings: list[Finding]


class ExportRequest(BaseModel):
    """Body of `POST /export`."""

    draft: Draft
    class_id: str
    object_id: str


class ExportResponse(BaseModel):
    """Body of the `/export` response: the three artefacts."""

    class_json: dict[str, Any]
    object_json: dict[str, Any]
    mappings: dict[str, Any]


class ImportRequest(BaseModel):
    """Body of `POST /import`."""

    family: str
    class_json: dict[str, Any]
    object_json: dict[str, Any]


def _catalogue(settings: Settings) -> dict[str, str]:
    return catalogue_types(load_catalogue(settings.catalogue_path))


@router.get("/families")
async def list_families() -> list[dict[str, Any]]:
    """Return every pass family, with the head fields its form needs."""
    return [
        {
            "family_id": descriptor.family_id,
            "label": descriptor.label,
            "head_fields": [field.model_dump() for field in descriptor.head_fields],
            "required_on_create": sorted(descriptor.required_on_create),
        }
        for descriptor in families.all_families()
    ]


@router.get("/personas")
async def list_personas(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> list[Persona]:
    """Return the preview personas, generated from the loaded catalogue."""
    return build_personas(load_catalogue(settings.catalogue_path))


@router.post("/validate")
async def validate_draft(
    request: ValidateRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ValidateResponse:
    """Return every problem with a draft, without exporting anything."""
    return ValidateResponse(findings=validate(request.draft, _catalogue(settings)))


@router.post("/export")
async def export_draft(
    request: ExportRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ExportResponse:
    """Return the three artefacts, refusing a draft that carries errors."""
    catalogue = _catalogue(settings)
    findings = validate(request.draft, catalogue)
    errors = [finding for finding in findings if finding.severity == "error"]
    if errors:
        raise HTTPException(
            status_code=422,
            detail=[finding.model_dump() for finding in errors],
        )

    class_json = build_class(request.draft, request.class_id)
    object_json = build_object(request.draft, request.object_id, request.class_id)
    return ExportResponse(
        class_json=class_json,
        object_json=object_json,
        mappings=build_mappings(object_json, catalogue),
    )


@router.post("/import")
async def import_artefacts(request: ImportRequest) -> Draft:
    """Return the draft that would export to the given class and object."""
    try:
        return read(request.class_json, request.object_json, family=request.family)
    except KeyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
