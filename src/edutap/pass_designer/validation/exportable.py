"""Checks that predict what the exporter would refuse."""

from ..draft.models import Draft, TransitOption
from ..platforms.google import families
from ._common import BARCODE_TYPES, FindingTemplate, bindings, is_url


def check_exportable(draft: Draft) -> list[FindingTemplate]:
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
    findings: list[FindingTemplate] = []

    if isinstance(draft.list_view.first_row, TransitOption):
        findings.append(
            FindingTemplate(
                severity="error",
                location="list/first row",
                msgid=(
                    "a transit list option is not supported yet; the "
                    "export would refuse it"
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
                FindingTemplate(
                    severity="error",
                    location=where,
                    msgid=(
                        "'%(key)s' is a localized head field, which is not "
                        "supported yet; the export would refuse it"
                    ),
                    params={"key": key},
                )
            )
        elif kind == "image_uri":
            if bindings(value):
                # A class-scoped binding is already reported, with the better
                # reason, by `check_head_values`.
                if scopes.get(key) != "class":
                    findings.append(
                        FindingTemplate(
                            severity="error",
                            location=where,
                            msgid=(
                                "'%(key)s' is an image field and cannot "
                                "carry a placeholder; upstream types the "
                                "image URI as a strict URL"
                            ),
                            params={"key": key},
                        )
                    )
            elif not is_url(value):
                findings.append(
                    FindingTemplate(
                        severity="error",
                        location=where,
                        msgid=(
                            "'%(key)s' must be a URL Google can fetch; "
                            "'%(value)s' is not one"
                        ),
                        params={"key": key, "value": value},
                    )
                )

    barcode_type = draft.redemption.barcode_type
    if barcode_type and barcode_type not in BARCODE_TYPES:
        findings.append(
            FindingTemplate(
                severity="error",
                location="barcode",
                msgid=(
                    "'%(barcode_type)s' is not a barcode type Google knows; "
                    "the export would refuse it"
                ),
                params={"barcode_type": barcode_type},
            )
        )

    for module in draft.image_modules:
        if module.bound or not module.uri:
            continue
        if not is_url(module.uri):
            findings.append(
                FindingTemplate(
                    severity="error",
                    location=f"image module '{module.module_id}'",
                    msgid=(
                        "image module '%(module_id)s' must be a URL Google "
                        "can fetch; '%(value)s' is not one"
                    ),
                    params={"module_id": module.module_id, "value": module.uri},
                )
            )

    return findings
