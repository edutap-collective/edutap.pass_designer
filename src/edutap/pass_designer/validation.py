"""Checks the Pydantic models cannot make.

The most important one is the first. Google discards a `fieldPath` that
refers to a module the object does not carry — silently. The row simply does
not appear, with no error at any layer, which makes it the one defect that
cannot be found by looking at either side alone.
"""

from collections.abc import Mapping
from typing import Literal

from edutap.wallet_google.models.datatypes.enums import BarcodeType
from pydantic import AnyUrl, BaseModel, TypeAdapter, ValidationError

from .draft.models import Cell, Draft, Line, TransitOption
from .placeholders import FIELD_KEY_PATTERN, check_dollar_signs, scan
from .platforms.google import families

MODULE_LIMIT = 10
MODULE_WARNING_THRESHOLD = 6

Severity = Literal["error", "warning"]

#: The exporter builds `ImageUri(uri=...)`, whose `uri` is a strict `AnyUrl`
#: upstream. Validating with the same adapter means this check and the export
#: cannot disagree about what counts as a URL.
_URL_ADAPTER: TypeAdapter[AnyUrl] = TypeAdapter(AnyUrl)

_BARCODE_TYPES = frozenset(member.value for member in BarcodeType)


def _is_url(value: str) -> bool:
    """Return True when the exporter would accept `value` as an image URI."""
    try:
        _URL_ADAPTER.validate_python(value)
    except ValidationError:
        return False
    return True


def _bindings(text: str) -> list[str]:
    """Return every field key bound inside `text`, in order."""
    return [field_key for _, field_key in scan(text)]


class Finding(BaseModel):
    """One problem with a draft."""

    severity: Severity
    message: str
    location: str


# Every surface of `Draft` that can carry a `Line` (and therefore a
# `fieldPath`) must be visited here. A surface left out is a silent Google
# defect with no way to notice it except reading this list against the
# model. As of this writing that is:
#   - front_rows        (Row -> Cell -> first/second)
#   - back_items         (Cell -> first/second)
#   - list_view          (first_row, second_row; first_row may be a
#                         TransitOption instead of a Line)
#   - barcode_section     (first_top, second_top, first_bottom)
# When `Draft` grows a new field that can hold a `Line`, `_lines` grows with
# it.
def _lines(draft: Draft) -> list[tuple[str, Line]]:
    found: list[tuple[str, Line]] = []

    def collect(where: str, cell: Cell) -> None:
        for line in (cell.first, cell.second):
            if line is not None:
                found.append((where, line))

    for row_index, row in enumerate(draft.front_rows):
        for cell_index, cell in enumerate(row.cells):
            collect(f"front/row {row_index + 1}/cell {cell_index + 1}", cell)
    for item_index, cell in enumerate(draft.back_items):
        collect(f"back/item {item_index + 1}", cell)
    for name, line in (
        ("list/first row", draft.list_view.first_row),
        ("list/second row", draft.list_view.second_row),
    ):
        if isinstance(line, Line):
            found.append((name, line))
    if draft.barcode_section is not None:
        for name, line in (
            ("barcode/first top", draft.barcode_section.first_top),
            ("barcode/second top", draft.barcode_section.second_top),
            ("barcode/first bottom", draft.barcode_section.first_bottom),
        ):
            if line is not None:
                found.append((name, line))
    return found


def _check_field_paths(draft: Draft) -> list[Finding]:
    text_ids = {module.module_id for module in draft.text_modules}
    image_ids = {module.module_id for module in draft.image_modules}
    findings: list[Finding] = []
    for where, line in _lines(draft):
        for reference in line.fallback_chain:
            known = text_ids if reference.kind == "text" else image_ids
            if reference.module_id not in known:
                findings.append(
                    Finding(
                        severity="error",
                        location=where,
                        message=(
                            f"no {reference.kind} module '{reference.module_id}' "
                            f"exists; Google discards this reference without "
                            f"reporting it and the value never appears"
                        ),
                    )
                )
    return findings


def _check_required_head_fields(draft: Draft) -> list[Finding]:
    descriptor = families.get(draft.family)
    findings: list[Finding] = []
    for key in sorted(descriptor.required_on_create):
        if key == "reviewStatus":
            continue  # carries a default in the upstream model
        if not draft.head.get(key):
            findings.append(
                Finding(
                    severity="error",
                    location="head",
                    message=f"Google requires '{key}' when the class is created",
                )
            )
    return findings


def _check_volume(draft: Draft) -> list[Finding]:
    findings: list[Finding] = []
    for label, count in (
        ("text modules", len(draft.text_modules)),
        ("links", len(draft.link_modules)),
    ):
        if count > MODULE_LIMIT:
            findings.append(
                Finding(
                    severity="error",
                    location=label,
                    message=(
                        f"{count} {label}; Google accepts at most {MODULE_LIMIT} "
                        f"and drops the rest without reporting it"
                    ),
                )
            )
        elif count >= MODULE_WARNING_THRESHOLD:
            findings.append(
                Finding(
                    severity="warning",
                    location=label,
                    message=f"{count} {label}; the limit is {MODULE_LIMIT}",
                )
            )
    return findings


def _check_bound_value(
    where: str, value: str, catalogue: Mapping[str, str]
) -> list[Finding]:
    """Check a value the designer marked as bound to a provider field."""
    if not value:
        return [
            Finding(
                severity="error",
                location=where,
                message=(
                    "is marked as bound but names no field; it would export as "
                    "'${}', import back as constant text, and then fail to "
                    "export again"
                ),
            )
        ]
    if not FIELD_KEY_PATTERN.match(value):
        return [
            Finding(
                severity="error",
                location=where,
                message=(
                    f"'{value}' is not a field key; a binding is a dotted "
                    f"identifier such as 'person.display_name'"
                ),
            )
        ]
    if value not in catalogue:
        return [
            Finding(
                severity="warning",
                location=where,
                message=(
                    f"'{value}' is not in the field catalogue; the pass builder "
                    f"will not be able to fill it"
                ),
            )
        ]
    return []


def _check_constant(where: str, value: str) -> list[Finding]:
    """Check a value that is written through to Google unchanged."""
    return [
        Finding(severity="error", location=where, message=problem)
        for problem in check_dollar_signs(value)
    ]


def _check_head_values(draft: Draft, catalogue: Mapping[str, str]) -> list[Finding]:
    """Check the head fields, where binding depends on which side they land on.

    A class-scoped head field cannot be bound. The class IS the template: one
    class serves every pass issued from it, so a per-person value has no
    meaning there. Written through, the cardholder sees the literal
    `${affiliation.primary}` as the issuer of their card.
    """
    scopes = {
        field.key: field.scope for field in families.get(draft.family).head_fields
    }
    findings: list[Finding] = []
    for key, value in sorted(draft.head.items()):
        where = f"head/{key}"
        bindings = _bindings(value)
        if not bindings:
            findings.extend(_check_constant(where, value))
            continue
        scope = scopes.get(key)
        if scope is None:
            # The descriptor does not declare this key, so the exporter drops
            # it. `_check_required_head_fields` owns what must be present.
            continue
        if scope == "class":
            findings.append(
                Finding(
                    severity="error",
                    location=where,
                    message=(
                        f"'{key}' is part of the class, which is the template "
                        f"shared by every pass, so it cannot be bound to "
                        f"'{bindings[0]}'; only object-scoped fields differ per "
                        f"person"
                    ),
                )
            )
            continue
        for field_key in bindings:
            findings.extend(_check_bound_value(where, field_key, catalogue))
    return findings


def _check_values(draft: Draft, catalogue: Mapping[str, str]) -> list[Finding]:
    """Check every string a draft carries into an export.

    The design says the export refuses a lone `$`. It has to refuse it
    everywhere, not only in text modules: a stray dollar sign reaches the
    cardholder as a literal `$` from whichever surface it sat on.
    """
    findings = _check_head_values(draft, catalogue)

    for module in draft.text_modules:
        where = f"module '{module.module_id}'"
        if module.bound:
            findings.extend(_check_bound_value(where, module.value, catalogue))
        else:
            findings.extend(_check_constant(where, module.value))

    for module in draft.image_modules:
        where = f"image module '{module.module_id}'"
        if module.bound:
            findings.extend(_check_bound_value(where, module.uri, catalogue))
        else:
            findings.extend(_check_constant(where, module.uri))

    for index, link in enumerate(draft.link_modules):
        where = f"link {index + 1}"
        findings.extend(_check_constant(where, link.uri))
        if link.description:
            findings.extend(_check_constant(where, link.description))

    for label, value in (
        ("barcode value", draft.redemption.barcode_value),
        ("smart tap value", draft.redemption.redemption_value),
    ):
        if value:
            findings.extend(_check_constant(label, value))

    return findings


def _check_exportable(draft: Draft) -> list[Finding]:
    """Predict what the exporter would refuse.

    Without these, a draft passes validation and then fails the export. That
    is the worst division of labour available: `/validate` is what an editor
    calls on every keystroke, `/export` what a person presses once at the end.
    The exporter keeps its own guards; they are the backstop, not the first
    line.
    """
    descriptor = families.get(draft.family)
    kinds = {field.key: field.kind for field in descriptor.head_fields}
    scopes = {field.key: field.scope for field in descriptor.head_fields}
    findings: list[Finding] = []

    if isinstance(draft.list_view.first_row, TransitOption):
        findings.append(
            Finding(
                severity="error",
                location="list/first row",
                message=(
                    "a transit list option is not supported yet; the export "
                    "would refuse it"
                ),
            )
        )

    for key, value in sorted(draft.head.items()):
        if not value:
            continue
        where = f"head/{key}"
        kind = kinds.get(key)
        if kind == "localized_text":
            findings.append(
                Finding(
                    severity="error",
                    location=where,
                    message=(
                        f"'{key}' is a localized head field, which is not "
                        f"supported yet; the export would refuse it"
                    ),
                )
            )
        elif kind == "image_uri":
            if _bindings(value):
                # A class-scoped binding is already reported, with the better
                # reason, by `_check_head_values`.
                if scopes.get(key) != "class":
                    findings.append(
                        Finding(
                            severity="error",
                            location=where,
                            message=(
                                f"'{key}' is an image field and cannot carry a "
                                f"placeholder; upstream types the image URI as "
                                f"a strict URL"
                            ),
                        )
                    )
            elif not _is_url(value):
                findings.append(
                    Finding(
                        severity="error",
                        location=where,
                        message=(
                            f"'{key}' must be a URL Google can fetch; "
                            f"'{value}' is not one"
                        ),
                    )
                )

    barcode_type = draft.redemption.barcode_type
    if barcode_type and barcode_type not in _BARCODE_TYPES:
        findings.append(
            Finding(
                severity="error",
                location="barcode",
                message=(
                    f"'{barcode_type}' is not a barcode type Google knows; the "
                    f"export would refuse it"
                ),
            )
        )

    for module in draft.image_modules:
        if module.bound or not module.uri:
            continue
        if not _is_url(module.uri):
            findings.append(
                Finding(
                    severity="error",
                    location=f"image module '{module.module_id}'",
                    message=(
                        f"image module '{module.module_id}' must be a URL "
                        f"Google can fetch; '{module.uri}' is not one"
                    ),
                )
            )

    return findings


def validate(draft: Draft, catalogue: Mapping[str, str]) -> list[Finding]:
    """Return every problem found, errors and warnings together."""
    return [
        *_check_field_paths(draft),
        *_check_required_head_fields(draft),
        *_check_volume(draft),
        *_check_values(draft, catalogue),
        *_check_exportable(draft),
    ]
