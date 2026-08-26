"""Read an exported class and object back into a `Draft`.

Anything this module does not understand is kept in `Draft.unmapped` and
written back unchanged on the next export. A tool that silently drops fields
when opening and saving is used exactly once.

This is the mirror of `exporter.class_json` and `exporter.object_json`, and
it has to track three rulings those two apply on the way out:

- **Head fields are scoped** (Task 4's `HeadField.scope`). `build_class`
  writes only class-scoped head fields; `build_object` writes only
  object-scoped ones (`accountName`, `accountId` for Loyalty). So `read()`
  collects each field from whichever document its own `scope` says it lives
  on, not from `class_json` alone.
- **An `image_uri` head field is wrapped** as
  `{"sourceUri": {"uri": "..."}}` on export; it has to be unwrapped back to
  the plain string `draft.head` holds.
- **A `localized_text` head field has no export path at all** — see
  `_head_fields.convert_head_value`, which raises rather than mis-map one.
  Nothing currently declares one, but if a document ever carries a value
  under such a key, this module does not attempt to parse it into a string:
  it leaves the raw value where it is, in `unmapped`. That keeps a future
  `build_class`/`build_object` call from raising on a value this importer
  never actually understood, and it is exactly the "keep what you don't
  understand" rule this module opens with.
"""

import re
from typing import Any

from ..draft.models import (
    BarcodeSection,
    Cell,
    Draft,
    FieldRef,
    ImageModuleDraft,
    Line,
    LinkModuleDraft,
    ListView,
    RedemptionSettings,
    Row,
    TextModuleDraft,
)
from ..placeholders import is_placeholder, source_field
from ..platforms.google import families
from ..platforms.google.families import FamilyDescriptor, HeadField

_FIELD_PATH = re.compile(r"^object\.(textModulesData|imageModulesData)\['([^']+)'\]$")

# Keys `build_class`/`build_object` set explicitly on the payload they hand to
# the upstream model — not everything the model's own `model_dump` fills in
# with a default (e.g. `reviewStatus`, `notifyPreference`). Those defaults are
# not decisions either exporter made, so they are left for `unmapped` to
# carry, same as any other field this module does not recognise.
_CLASS_KEYS_HANDLED = {
    "id",
    "classTemplateInfo",
    "enableSmartTap",
    "redemptionIssuers",
}
_OBJECT_KEYS_HANDLED = {
    "id",
    "classId",
    "textModulesData",
    "imageModulesData",
    "linksModuleData",
    "smartTapRedemptionValue",
    "barcode",
}


def _reference(field_path: str) -> FieldRef | None:
    match = _FIELD_PATH.match(field_path)
    if match is None:
        return None
    collection, module_id = match.groups()
    kind = "text" if collection == "textModulesData" else "image"
    return FieldRef(kind=kind, module_id=module_id)


def _line(selector: dict[str, Any] | None) -> Line | None:
    if not selector:
        return None
    references = [
        reference
        for reference in (
            _reference(field.get("fieldPath", ""))
            for field in selector.get("fields", [])
        )
        if reference is not None
    ]
    return Line(fallback_chain=references) if references else None


def _cell(item: dict[str, Any] | None) -> Cell:
    if not item:
        return Cell()
    return Cell(
        first=_line(item.get("firstValue")), second=_line(item.get("secondValue"))
    )


def _row(entry: dict[str, Any]) -> Row | None:
    if "oneItem" in entry:
        return Row(cells=[_cell(entry["oneItem"].get("item"))])
    if "twoItems" in entry:
        two = entry["twoItems"]
        return Row(cells=[_cell(two.get("startItem")), _cell(two.get("endItem"))])
    if "threeItems" in entry:
        three = entry["threeItems"]
        return Row(
            cells=[
                _cell(three.get("startItem")),
                _cell(three.get("middleItem")),
                _cell(three.get("endItem")),
            ]
        )
    return None


def _head_field_source(
    field: HeadField, class_json: dict[str, Any], object_json: dict[str, Any]
) -> dict[str, Any]:
    """Return whichever document `field.scope` says this key was written to."""
    return class_json if field.scope == "class" else object_json


def _head_value(field: HeadField, raw: Any) -> str | None:
    """Undo `_head_fields.convert_head_value` for one field.

    `image_uri` is unwrapped from `{"sourceUri": {"uri": ...}}` back to the
    plain string. Everything else (`text`, `colour`, `enum`) was written
    through as-is, so it comes back the same way. `localized_text` is never
    reached here — see `_restorable_head_fields`.
    """
    if field.kind == "image_uri":
        if not isinstance(raw, dict):
            return None
        uri = raw.get("sourceUri", {}).get("uri")
        return uri or None
    return raw


def _restorable_head_fields(descriptor: FamilyDescriptor) -> list[HeadField]:
    """Head fields this module can actually turn back into a plain string.

    `localized_text` is excluded on purpose: there is no export path for it
    (`convert_head_value` raises), so there is nothing to mirror on import
    either. Excluding it here also keeps its key out of the "known" sets
    below, so a `localized_text` value found in either document is preserved
    verbatim in `unmapped` rather than silently dropped.
    """
    return [field for field in descriptor.head_fields if field.kind != "localized_text"]


def _head(
    descriptor: FamilyDescriptor,
    class_json: dict[str, Any],
    object_json: dict[str, Any],
) -> dict[str, str]:
    head: dict[str, str] = {}
    for field in _restorable_head_fields(descriptor):
        source = _head_field_source(field, class_json, object_json)
        if field.key not in source:
            continue
        value = _head_value(field, source[field.key])
        if value is not None:
            head[field.key] = value
    return head


def read(class_json: dict[str, Any], object_json: dict[str, Any], family: str) -> Draft:
    """Return the `Draft` that would export to `class_json` and `object_json`."""
    descriptor = families.get(family)
    template = class_json.get("classTemplateInfo", {})

    card = template.get("cardTemplateOverride", {}).get("cardRowTemplateInfos", [])
    front_rows = [row for row in (_row(entry) for entry in card) if row is not None]

    details = template.get("detailsTemplateOverride", {}).get("detailsItemInfos", [])
    back_items = [_cell(entry.get("item")) for entry in details]

    list_override = template.get("listTemplateOverride", {})
    list_view = ListView(
        first_row=_line(list_override.get("firstRowOption", {}).get("fieldOption")),
        second_row=_line(list_override.get("secondRowOption")),
    )

    # classTemplateInfo counts as handled, so anything inside it that is not
    # restored here is lost rather than kept in `unmapped`.
    section_json = template.get("cardBarcodeSectionDetails") or {}
    barcode_section = None
    if section_json:
        barcode_section = BarcodeSection(
            first_top=_line(
                section_json.get("firstTopDetail", {}).get("fieldSelector")
            ),
            second_top=_line(
                section_json.get("secondTopDetail", {}).get("fieldSelector")
            ),
            first_bottom=_line(
                section_json.get("firstBottomDetail", {}).get("fieldSelector")
            ),
        )

    head = _head(descriptor, class_json, object_json)

    text_modules = [
        TextModuleDraft(
            module_id=module["id"],
            header=module.get("header"),
            value=source_field(module.get("body", "")) or module.get("body", ""),
            bound=is_placeholder(module.get("body", "")),
        )
        for module in object_json.get("textModulesData", [])
        if module.get("id")
    ]

    image_modules = []
    for module in object_json.get("imageModulesData", []):
        uri = module.get("mainImage", {}).get("sourceUri", {}).get("uri", "")
        if module.get("id"):
            image_modules.append(
                ImageModuleDraft(
                    module_id=module["id"],
                    uri=source_field(uri) or uri,
                    bound=is_placeholder(uri),
                )
            )

    link_modules = [
        LinkModuleDraft(uri=entry.get("uri", ""), description=entry.get("description"))
        for entry in object_json.get("linksModuleData", {}).get("uris", [])
    ]

    barcode = object_json.get("barcode") or {}
    redemption = RedemptionSettings(
        smart_tap_enabled=bool(class_json.get("enableSmartTap")),
        redemption_issuers=list(class_json.get("redemptionIssuers", [])),
        redemption_value=object_json.get("smartTapRedemptionValue"),
        barcode_type=barcode.get("type"),
        barcode_value=barcode.get("value"),
    )

    restorable = _restorable_head_fields(descriptor)
    known_class_keys = _CLASS_KEYS_HANDLED | {
        field.key for field in restorable if field.scope == "class"
    }
    known_object_keys = _OBJECT_KEYS_HANDLED | {
        field.key for field in restorable if field.scope == "object"
    }
    unmapped = {
        "class": {k: v for k, v in class_json.items() if k not in known_class_keys},
        "object": {k: v for k, v in object_json.items() if k not in known_object_keys},
    }

    return Draft(
        family=family,
        head=head,
        front_rows=front_rows,
        barcode_section=barcode_section,
        back_items=back_items,
        list_view=list_view,
        text_modules=text_modules,
        image_modules=image_modules,
        link_modules=link_modules,
        redemption=redemption,
        unmapped=unmapped,
    )
