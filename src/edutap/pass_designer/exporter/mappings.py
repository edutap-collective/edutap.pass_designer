"""Derive the binding table from the placeholders in an exported object.

The shape is `MappingRulesRequest` from `edutap.pass_builder`, so the same
payload can be written to a file today and sent to
`PUT /versions/{id}/mappings` later. Nothing new is invented here.
"""

from collections.abc import Mapping
from typing import Any

from ..placeholders import scan


def build_mappings(
    object_json: Mapping[str, Any], catalogue: Mapping[str, str]
) -> dict[str, Any]:
    """Return `{"rules": [...], "unknown_fields": [...]}` for `object_json`.

    `catalogue` maps a data-provider field key to its value-type slug. A field
    the catalogue does not know still produces a rule — dropping it would hide
    the binding entirely — but it is reported so the caller can refuse to
    export.
    """
    rules: list[dict[str, Any]] = []
    unknown: list[str] = []
    for position, (pointer, field_key) in enumerate(scan(object_json)):
        value_type = catalogue.get(field_key)
        if value_type is None:
            unknown.append(field_key)
            value_type = "text"
        rules.append(
            {
                "target_kind": "json_pointer",
                "target": pointer,
                "source_field": field_key,
                "value_type": value_type,
                "required": True,
                "default_value": None,
                "position": position,
            }
        )
    return {"rules": rules, "unknown_fields": sorted(set(unknown))}
