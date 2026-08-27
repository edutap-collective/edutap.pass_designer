"""Checks on every string a draft carries into an export."""

from collections.abc import Mapping

from ..draft.models import Draft
from ..platforms.google import families
from ._common import FindingTemplate, bindings, check_bound_value, check_constant


def check_head_values(
    draft: Draft, catalogue: Mapping[str, str]
) -> list[FindingTemplate]:
    """Check the head fields, where binding depends on which side they land on.

    A class-scoped head field cannot be bound. The class IS the template: one
    class serves every pass issued from it, so a per-person value has no
    meaning there. Written through, the cardholder sees the literal
    `${affiliation.primary}` as the issuer of their card.
    """
    scopes = {
        field.key: field.scope for field in families.get(draft.family).head_fields
    }
    findings: list[FindingTemplate] = []
    for key, value in sorted(draft.head.items()):
        where = f"head/{key}"
        bound_keys = bindings(value)
        if not bound_keys:
            findings.extend(check_constant(where, value))
            continue
        scope = scopes.get(key)
        if scope is None:
            # The descriptor does not declare this key, so the exporter drops
            # it. `check_required_head_fields` owns what must be present.
            continue
        if scope == "class":
            findings.append(
                FindingTemplate(
                    severity="error",
                    location=where,
                    msgid=(
                        "'%(key)s' is part of the class, which is the "
                        "template shared by every pass, so it cannot be "
                        "bound to '%(field_key)s'; only object-scoped "
                        "fields differ per person"
                    ),
                    params={"key": key, "field_key": bound_keys[0]},
                )
            )
            continue
        for field_key in bound_keys:
            findings.extend(check_bound_value(where, field_key, catalogue))
    return findings


def check_values(draft: Draft, catalogue: Mapping[str, str]) -> list[FindingTemplate]:
    """Check every string a draft carries into an export.

    The design says the export refuses a lone `$`. It has to refuse it
    everywhere, not only in text modules: a stray dollar sign reaches the
    cardholder as a literal `$` from whichever surface it sat on.
    """
    findings = check_head_values(draft, catalogue)

    for module in draft.text_modules:
        where = f"module '{module.module_id}'"
        if module.bound:
            findings.extend(check_bound_value(where, module.value, catalogue))
        else:
            findings.extend(check_constant(where, module.value))

    for module in draft.image_modules:
        where = f"image module '{module.module_id}'"
        if module.bound:
            findings.extend(check_bound_value(where, module.uri, catalogue))
        else:
            findings.extend(check_constant(where, module.uri))

    for index, link in enumerate(draft.link_modules):
        where = f"link {index + 1}"
        findings.extend(check_constant(where, link.uri))
        if link.description:
            findings.extend(check_constant(where, link.description))

    for label, value in (
        ("barcode value", draft.redemption.barcode_value),
        ("smart tap value", draft.redemption.redemption_value),
    ):
        if value:
            findings.extend(check_constant(label, value))

    return findings
