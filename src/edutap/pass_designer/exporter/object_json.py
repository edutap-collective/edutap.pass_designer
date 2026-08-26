"""Translate a `Draft` into the family's Google Wallet object."""

from typing import Any

from edutap.wallet_google.models.datatypes.barcode import Barcode
from edutap.wallet_google.models.datatypes.data import (
    ImageModuleData,
    LinksModuleData,
    TextModuleData,
)
from edutap.wallet_google.models.datatypes.general import Image, ImageUri, Uri

from ..draft.models import Draft
from ..placeholders import placeholder_for
from ..platforms.google import families
from ..platforms.google.families import FamilyDescriptor
from ._head_fields import convert_head_value


def _value(raw: str, bound: bool) -> str:
    """Return a placeholder for a bound value, the text itself otherwise."""
    return placeholder_for(raw) if bound else raw


def _sentinel_image_uri(module_id: str) -> str:
    """Return a syntactically valid URI that stands in for a bound image.

    `ImageUri.uri` is a strict `AnyUrl` upstream — unlike `Uri.uri`, which
    accepts `AnyUrl | str | None` — so a `${field}` placeholder can never pass
    through it directly; construction would raise a `ValidationError` before
    the model dump is ever reached. This sentinel exists only to satisfy that
    validation; the real placeholder is written back in afterwards, by index,
    once the model has done its job for everything else. Do not delete this
    without keeping the post-dump substitution below in sync.
    """
    return f"https://placeholder.invalid/{module_id}"


def _head_payload(descriptor: FamilyDescriptor, head: dict[str, str]) -> dict[str, Any]:
    """Copy the object-scoped head fields the family declares.

    The mirror image of `class_json._head_payload`. Task 4 gave `HeadField` a
    `scope`: `accountName` and `accountId` live on `LoyaltyObject`, not the
    class, and `build_class` correctly refuses them — but without this
    function reading `draft.head` too, they would vanish from every export
    instead of landing anywhere. A key `draft.head` carries that the
    descriptor does not declare at all is ignored outright, same as on the
    class side.

    The per-kind conversion is shared with `class_json._head_payload` via
    `_head_fields.convert_head_value`; only the scope filtered on differs,
    and that stays local rather than becoming a flag argument on a shared
    function.
    """
    fields_by_key = {field.key: field for field in descriptor.head_fields}
    payload: dict[str, Any] = {}
    for key, value in head.items():
        field = fields_by_key.get(key)
        if field is None or field.scope != "object":
            continue
        converted = convert_head_value(field, value)
        if converted is not None:
            payload[key] = converted
    return payload


def build_object(draft: Draft, object_id: str, class_id: str) -> dict[str, Any]:
    """Return the family's specimen object as a plain dict.

    Values marked `bound` are written as `${field}` and filled by the pass
    builder at issuing time; everything else is a constant of the template.
    """
    descriptor = families.get(draft.family)
    payload: dict[str, Any] = {
        "id": object_id,
        "classId": class_id,
        **_head_payload(descriptor, draft.head),
    }

    if draft.text_modules:
        payload["textModulesData"] = [
            TextModuleData(
                id=module.module_id,
                header=module.header,
                body=_value(module.value, module.bound),
            )
            for module in draft.text_modules
        ]

    if draft.image_modules:
        # `ImageUri.uri` is a strict `AnyUrl`, so a bound module's `${field}`
        # placeholder cannot be constructed here directly — see
        # `_sentinel_image_uri`. A syntactically valid sentinel goes into the
        # model instead, and the real placeholder is patched back in below,
        # by index, once the model has validated everything else.
        payload["imageModulesData"] = [
            ImageModuleData(
                id=module.module_id,
                mainImage=Image(
                    sourceUri=ImageUri(
                        uri=_sentinel_image_uri(module.module_id)
                        if module.bound
                        else module.uri
                    )
                ),
            )
            for module in draft.image_modules
        ]

    if draft.link_modules:
        payload["linksModuleData"] = LinksModuleData(
            uris=[
                Uri(uri=link.uri, description=link.description)
                for link in draft.link_modules
            ]
        )

    redemption = draft.redemption
    if redemption.redemption_value is not None:
        payload["smartTapRedemptionValue"] = redemption.redemption_value

    # No barcode key at all when none is wanted. This is the case Google's own
    # pass builder cannot express, and it is the normal case for us.
    if redemption.barcode_type:
        payload["barcode"] = Barcode(
            type=redemption.barcode_type, value=redemption.barcode_value or ""
        )

    wallet_object = descriptor.object_model(**payload)
    exported = wallet_object.model_dump(exclude_none=True, mode="json")

    # Patch the real placeholders back in, by index into `draft.image_modules`
    # — never by string matching the sentinel, so no real URI can ever
    # collide with it. This has to happen before the `unmapped` merge below,
    # so a preserved `unmapped` value can still win where that ruling says it
    # should.
    for index, module in enumerate(draft.image_modules):
        if module.bound:
            exported["imageModulesData"][index]["mainImage"]["sourceUri"]["uri"] = (
                placeholder_for(module.uri)
            )

    # Same reasoning as `class_json.build_class`: `exported` is a full
    # model_dump, so it always carries a value for every field with a
    # non-None default, whether or not this function ever set it. `exported`
    # wins only for keys this function actually decided (`payload`); for
    # anything else, a preserved value in `draft.unmapped["object"]` wins,
    # defaults included.
    preserved = draft.unmapped.get("object", {})
    carried = {key: value for key, value in preserved.items() if key not in payload}
    return {**exported, **carried}
