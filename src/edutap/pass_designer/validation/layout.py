"""Checks on the shape of a draft: references, required fields, volume."""

from ..draft.models import Cell, Draft, Line
from ..platforms.google import families
from ._common import MODULE_LIMIT, MODULE_WARNING_THRESHOLD, FindingTemplate


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


def check_field_paths(draft: Draft) -> list[FindingTemplate]:
    """Check that every `fieldPath` names a module the object carries.

    This is the check the whole package exists for: Google discards an
    unknown reference silently, so the row just never appears and nothing
    anywhere reports it.
    """
    text_ids = {module.module_id for module in draft.text_modules}
    image_ids = {module.module_id for module in draft.image_modules}
    findings: list[FindingTemplate] = []
    for where, line in _lines(draft):
        for reference in line.fallback_chain:
            known = text_ids if reference.kind == "text" else image_ids
            if reference.module_id not in known:
                findings.append(
                    FindingTemplate(
                        severity="error",
                        location=where,
                        msgid=(
                            "no %(kind)s module '%(module_id)s' exists; "
                            "Google discards this reference without "
                            "reporting it and the value never appears"
                        ),
                        params={
                            "kind": reference.kind,
                            "module_id": reference.module_id,
                        },
                    )
                )
    return findings


def check_duplicate_module_ids(draft: Draft) -> list[FindingTemplate]:
    """Check that no two modules of the same kind share a `module_id`.

    The editor generates ids client-side; an imported artefact can carry a
    gap in its own numbering, and a freshly generated id can land on it. Two
    modules sharing an id means two `textModulesData` (or `imageModulesData`)
    entries with the same id in the exported object and an ambiguous
    `fieldPath` — Google's behaviour in that case is undefined, and nothing
    downstream would ever say why a value looked wrong. This check is the
    layer that must not let such an artefact out, whatever produced it.
    """
    findings: list[FindingTemplate] = []
    for label, modules in (
        ("text", draft.text_modules),
        ("image", draft.image_modules),
    ):
        seen: set[str] = set()
        duplicates: set[str] = set()
        for module in modules:
            if module.module_id in seen:
                duplicates.add(module.module_id)
            seen.add(module.module_id)
        for module_id in sorted(duplicates):
            findings.append(
                FindingTemplate(
                    severity="error",
                    location=f"{label} modules",
                    msgid=(
                        "more than one %(kind)s module uses the id "
                        "'%(module_id)s'; Google's behaviour when two "
                        "modules share an id is undefined and the "
                        "exported fieldPath becomes ambiguous"
                    ),
                    params={"kind": label, "module_id": module_id},
                )
            )
    return findings


def check_required_head_fields(draft: Draft) -> list[FindingTemplate]:
    """Check the fields Google demands when the class is created.

    The Pydantic models are more permissive than the API, so a draft can
    validate cleanly and still be rejected on insert.
    """
    descriptor = families.get(draft.family)
    findings: list[FindingTemplate] = []
    for key in sorted(descriptor.required_on_create):
        if key == "reviewStatus":
            continue  # carries a default in the upstream model
        if not draft.head.get(key):
            findings.append(
                FindingTemplate(
                    severity="error",
                    location="head",
                    msgid="Google requires '%(key)s' when the class is created",
                    params={"key": key},
                )
            )
    return findings


def check_volume(draft: Draft) -> list[FindingTemplate]:
    """Warn as a draft approaches Google's module limits, and refuse past them.

    Google accepts at most ten and drops the rest without reporting it.
    """
    findings: list[FindingTemplate] = []
    for label, count in (
        ("text modules", len(draft.text_modules)),
        ("links", len(draft.link_modules)),
    ):
        if count > MODULE_LIMIT:
            findings.append(
                FindingTemplate(
                    severity="error",
                    location=label,
                    msgid=(
                        "%(count)d %(label)s; Google accepts at most "
                        "%(limit)d and drops the rest without reporting it"
                    ),
                    params={
                        "count": count,
                        "label": label,
                        "limit": MODULE_LIMIT,
                    },
                )
            )
        elif count >= MODULE_WARNING_THRESHOLD:
            findings.append(
                FindingTemplate(
                    severity="warning",
                    location=label,
                    msgid="%(count)d %(label)s; the limit is %(limit)d",
                    params={
                        "count": count,
                        "label": label,
                        "limit": MODULE_LIMIT,
                    },
                )
            )
    return findings
