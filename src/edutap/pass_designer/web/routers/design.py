"""The routes the editor consumes."""

from typing import Annotated, Any

import anyio.to_thread
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ValidationError

from ...draft.models import Draft
from ...exporter.class_json import build_class
from ...exporter.mappings import build_mappings
from ...exporter.object_json import build_object
from ...i18n import negotiate
from ...importer.reader import read
from ...personas.catalogue import (
    CatalogueError,
    CatalogueField,
    catalogue_types,
    load_catalogue,
)
from ...personas.generator import Persona, build_personas
from ...platforms.google import families
from ...platforms.google.families import HeadField
from ...settings import Settings, get_settings
from ...validation import Finding, validate

router = APIRouter(prefix="/designer/v1", tags=["designer"])


def language(
    accept_language: Annotated[str | None, Header()] = None,
) -> str:
    """Resolve the caller's preferred language from `Accept-Language`."""
    return negotiate(accept_language)


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


class ExportErrorResponse(BaseModel):
    """Body of a `422`: the findings that blocked an export or an import.

    Not FastAPI's generic `HTTPValidationError` — the request body itself was
    well-formed, it is the *draft* (or, for `/import`, the artefacts handed
    in) that carries errors — so this is declared explicitly via `responses=`
    on the route rather than left to the default, which would otherwise
    mislead a client generated from the OpenAPI schema.
    """

    detail: list[Finding]


class ImportErrorResponse(BaseModel):
    """Body of a `400`: an unknown or empty pass family, as plain text."""

    detail: str


class CatalogueErrorResponse(BaseModel):
    """Body of a `500` caused by a malformed catalogue file on disk.

    This is the one case where `500` is the right status: the request itself
    was fine, it is the *server's* configuration that is broken. The body
    still has to be JSON, and it has to name the offending file so whoever
    deployed a bad catalogue can find it.
    """

    detail: str


class ImportRequest(BaseModel):
    """Body of `POST /import`."""

    family: str
    class_json: dict[str, Any]
    object_json: dict[str, Any]


class FamilyResponse(BaseModel):
    """Body of one entry in the `/families` response."""

    family_id: str
    label: str
    head_fields: list[HeadField]
    required_on_create: list[str]


async def _load_catalogue(settings: Settings) -> list[CatalogueField]:
    """Read the catalogue file off a worker thread.

    `Path.read_text()` inside `load_catalogue` is blocking I/O; the repository
    is async-first, so it does not belong directly in an `async def` handler.
    """
    return await anyio.to_thread.run_sync(load_catalogue, settings.catalogue_path)


async def _catalogue(settings: Settings) -> dict[str, str]:
    return catalogue_types(await _load_catalogue(settings))


def _catalogue_error(error: CatalogueError) -> HTTPException:
    """Turn a malformed catalogue file into a `500` with a JSON body."""
    return HTTPException(status_code=500, detail=str(error))


def _unknown_family_error(error: KeyError) -> HTTPException:
    """Turn an unknown (or empty) pass family into a `400` with a JSON body."""
    return HTTPException(status_code=400, detail=str(error))


def _export_findings(error: ValidationError | NotImplementedError) -> list[Finding]:
    """Turn an exception the exporter or importer could not avoid into findings.

    `pydantic.ValidationError` fires when a converted value fails validation
    on the upstream Google model — a non-URL image head field, a `${...}`
    where an image URI must be a real URL, an unknown barcode type, a
    malformed unbound image URI. `NotImplementedError` fires for a shape this
    tool does not support yet (a `TransitOption` in the list view, a
    `localized_text` head field). Either way `/validate` reported zero
    errors for the same draft, so the designer needs to see exactly what was
    rejected — not a bare `500 Internal Server Error`. The exception's own
    text is preserved in the message rather than paraphrased, so a designer
    can tell which value failed and why.
    """
    if isinstance(error, ValidationError):
        return [
            Finding(
                severity="error",
                location=".".join(str(part) for part in item["loc"]) or "draft",
                message=f"{item['msg']} (got {item.get('input')!r})",
            )
            for item in error.errors()
        ]
    return [Finding(severity="error", location="draft", message=str(error))]


def _export_error(error: ValidationError | NotImplementedError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=[finding.model_dump() for finding in _export_findings(error)],
    )


@router.get("/families")
async def list_families() -> list[FamilyResponse]:
    """Return every pass family, with the head fields its form needs."""
    return [
        FamilyResponse(
            family_id=descriptor.family_id,
            label=descriptor.label,
            head_fields=descriptor.head_fields,
            required_on_create=sorted(descriptor.required_on_create),
        )
        for descriptor in families.all_families()
    ]


@router.get("/personas")
async def list_personas(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> list[Persona]:
    """Return the preview personas, generated from the loaded catalogue."""
    return build_personas(await _load_catalogue(settings))


@router.get("/catalogue")
async def list_catalogue(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> list[CatalogueField]:
    """Return the fields a data provider can deliver.

    The editor binds values against this list, so a field key cannot be
    mistyped. `CatalogueField` is the shape `edutap.pass_builder` already
    defines; nothing new is invented here.
    """
    return await _load_catalogue(settings)


@router.post(
    "/validate",
    responses={
        400: {"model": ImportErrorResponse},
        500: {"model": CatalogueErrorResponse},
    },
)
async def validate_draft(
    request: ValidateRequest,
    lang: Annotated[str, Depends(language)],
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ValidateResponse:
    """Return every problem with a draft, without exporting anything."""
    try:
        catalogue = await _catalogue(settings)
    except CatalogueError as error:
        raise _catalogue_error(error) from error

    try:
        findings = validate(request.draft, catalogue, language=lang)
    except KeyError as error:
        raise _unknown_family_error(error) from error

    return ValidateResponse(findings=findings)


@router.post(
    "/export",
    responses={
        400: {"model": ImportErrorResponse},
        422: {"model": ExportErrorResponse},
        500: {"model": CatalogueErrorResponse},
    },
)
async def export_draft(
    request: ExportRequest,
    lang: Annotated[str, Depends(language)],
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ExportResponse:
    """Return the three artefacts, refusing a draft that carries errors."""
    try:
        catalogue = await _catalogue(settings)
    except CatalogueError as error:
        raise _catalogue_error(error) from error

    try:
        findings = validate(request.draft, catalogue, language=lang)
    except KeyError as error:
        raise _unknown_family_error(error) from error

    errors = [finding for finding in findings if finding.severity == "error"]
    if errors:
        raise HTTPException(
            status_code=422,
            detail=[finding.model_dump() for finding in errors],
        )

    # The draft passed `/validate` with zero errors, but validation cannot
    # anticipate every way the upstream Google models refuse a converted
    # value (a `TransitOption` in the list view, a non-URL image head field,
    # an unknown barcode type, a malformed unbound image URI). Those surface
    # here instead, and must not become a bare `500 text/plain` — a client
    # generated from this OpenAPI document needs the real contract.
    try:
        class_json = build_class(request.draft, request.class_id)
        object_json = build_object(request.draft, request.object_id, request.class_id)
    except KeyError as error:
        raise _unknown_family_error(error) from error
    except (ValidationError, NotImplementedError) as error:
        raise _export_error(error) from error

    return ExportResponse(
        class_json=class_json,
        object_json=object_json,
        mappings=build_mappings(object_json, catalogue),
    )


@router.post(
    "/import",
    responses={
        400: {"model": ImportErrorResponse},
        422: {"model": ExportErrorResponse},
    },
)
async def import_artefacts(request: ImportRequest) -> Draft:
    """Return the draft that would export to the given class and object."""
    try:
        return read(request.class_json, request.object_json, family=request.family)
    except KeyError as error:
        raise _unknown_family_error(error) from error
    except (ValidationError, NotImplementedError) as error:
        raise _export_error(error) from error
