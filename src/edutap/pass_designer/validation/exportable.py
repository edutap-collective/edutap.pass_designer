"""Checks that predict what the exporter would refuse."""

from ..draft.models import Draft, TransitOption
from ..platforms.google import families
from ._common import BARCODE_TYPES, Finding, bindings, is_url


def check_exportable(draft: Draft) -> list[Finding]:
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
            if bindings(value):
                # A class-scoped binding is already reported, with the better
                # reason, by `check_head_values`.
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
            elif not is_url(value):
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
    if barcode_type and barcode_type not in BARCODE_TYPES:
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
        if not is_url(module.uri):
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
