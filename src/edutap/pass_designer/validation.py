"""Checks the Pydantic models cannot make.

The most important one is the first. Google discards a `fieldPath` that
refers to a module the object does not carry — silently. The row simply does
not appear, with no error at any layer, which makes it the one defect that
cannot be found by looking at either side alone.
"""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel

from .draft.models import Cell, Draft, Line
from .placeholders import check_dollar_signs
from .platforms.google import families

MODULE_LIMIT = 10
MODULE_WARNING_THRESHOLD = 6

Severity = Literal["error", "warning"]


class Finding(BaseModel):
    """One problem with a draft."""

    severity: Severity
    message: str
    location: str


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


def _check_values(draft: Draft, catalogue: Mapping[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for module in draft.text_modules:
        where = f"module '{module.module_id}'"
        if module.bound:
            if module.value not in catalogue:
                findings.append(
                    Finding(
                        severity="warning",
                        location=where,
                        message=(
                            f"'{module.value}' is not in the field catalogue; "
                            f"the pass builder will not be able to fill it"
                        ),
                    )
                )
            continue
        for problem in check_dollar_signs(module.value):
            findings.append(Finding(severity="error", location=where, message=problem))
    return findings


def validate(draft: Draft, catalogue: Mapping[str, str]) -> list[Finding]:
    """Return every problem found, errors and warnings together."""
    return [
        *_check_field_paths(draft),
        *_check_required_head_fields(draft),
        *_check_volume(draft),
        *_check_values(draft, catalogue),
    ]
