"""The object carries constants as they are and bindings as placeholders."""

from edutap.pass_designer.draft.models import (
    Draft,
    ImageModuleDraft,
    RedemptionSettings,
    TextModuleDraft,
)
from edutap.pass_designer.exporter.mappings import build_mappings
from edutap.pass_designer.exporter.object_json import build_object
from edutap.pass_designer.placeholders import scan

CLASS_ID = "3388000000000000000.library.demo"
OBJECT_ID = "3388000000000000000.specimen.object"


def _draft(**overrides: object) -> Draft:
    return Draft(**{"family": "loyalty", **overrides})


def test_a_bound_module_becomes_a_placeholder() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(
                module_id="name",
                header="Name",
                value="person.display_name",
                bound=True,
            )
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["textModulesData"]

    assert modules[0]["body"] == "${person.display_name}"
    assert modules[0]["id"] == "name"


def test_a_constant_module_is_written_through() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(
                module_id="issuer", header="Issuer", value="Example University"
            )
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["textModulesData"]

    assert modules[0]["body"] == "Example University"


def test_an_image_module_carries_its_uri() -> None:
    draft = _draft(
        image_modules=[
            ImageModuleDraft(module_id="photo", uri="https://example.org/photo.png")
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["imageModulesData"]

    assert (
        modules[0]["mainImage"]["sourceUri"]["uri"] == "https://example.org/photo.png"
    )


def test_an_nfc_only_pass_emits_no_barcode_key_at_all() -> None:
    draft = _draft(
        redemption=RedemptionSettings(
            smart_tap_enabled=True, redemption_value="LIBRARY-CARD"
        )
    )

    result = build_object(draft, OBJECT_ID, CLASS_ID)

    assert "barcode" not in result
    assert result["smartTapRedemptionValue"] == "LIBRARY-CARD"


def test_a_barcode_is_emitted_when_one_is_wanted() -> None:
    draft = _draft(
        redemption=RedemptionSettings(barcode_type="AZTEC", barcode_value="12345")
    )

    barcode = build_object(draft, OBJECT_ID, CLASS_ID)["barcode"]

    assert barcode["type"] == "AZTEC"
    assert barcode["value"] == "12345"


# --- Ruling A: object-scoped head fields reach the object; class-scoped ones don't ---


def test_object_scoped_head_fields_reach_the_object() -> None:
    """`accountName` and `accountId` are declared with `scope="object"`.

    `build_class` correctly refuses them; without `build_object` reading
    `draft.head` too, they would vanish from every export.
    """
    draft = _draft(head={"accountName": "Jane Doe", "accountId": "12345"})

    result = build_object(draft, OBJECT_ID, CLASS_ID)

    assert result["accountName"] == "Jane Doe"
    assert result["accountId"] == "12345"


def test_a_class_scoped_head_field_is_not_written_to_the_object() -> None:
    """`programName` is scoped to `LoyaltyClass`; the object never sees it."""
    draft = _draft(head={"programName": "Library", "accountName": "Jane Doe"})

    result = build_object(draft, OBJECT_ID, CLASS_ID)

    assert "programName" not in result


# --- Ruling B: unmapped["object"] survives export; exporter decisions still win ---


def test_a_preserved_unmapped_value_survives_the_export_unchanged() -> None:
    """A preserved `unmapped["object"]` value beats the model's own default.

    `disableExpirationNotification` has a non-None default (`False`) on
    `LoyaltyObject`; `build_object` never sets it, so the only plausible
    source of a real value is `unmapped` — an importer carrying it forward
    from an already-issued object. A full `model_dump` would otherwise always
    report the model's own default instead.
    """
    draft = _draft(unmapped={"object": {"disableExpirationNotification": True}})

    result = build_object(draft, OBJECT_ID, CLASS_ID)

    assert result["disableExpirationNotification"] is True


def test_a_key_the_exporter_sets_is_not_overridden_by_a_stale_unmapped_copy() -> None:
    draft = _draft(
        head={"accountName": "Jane Doe"},
        unmapped={"object": {"accountName": "Stale Name"}},
    )

    result = build_object(draft, OBJECT_ID, CLASS_ID)

    assert result["accountName"] == "Jane Doe"


# --- Critical fix: a bound image module must not crash on the strict ImageUri ---


def test_a_bound_image_module_becomes_a_placeholder() -> None:
    """A bound image module must not crash on the strict upstream `ImageUri`.

    `ImageUri.uri` is a strict `AnyUrl` upstream, so a `${field}` placeholder
    cannot be constructed through it directly; the exported object must still
    end up carrying the placeholder.
    """
    draft = _draft(
        image_modules=[
            ImageModuleDraft(module_id="photo", uri="person.photo", bound=True)
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["imageModulesData"]

    assert modules[0]["mainImage"]["sourceUri"]["uri"] == "${person.photo}"


def test_a_bound_image_placeholder_is_found_by_scan() -> None:
    draft = _draft(
        image_modules=[
            ImageModuleDraft(module_id="photo", uri="person.photo", bound=True)
        ]
    )

    result = build_object(draft, OBJECT_ID, CLASS_ID)

    assert scan(result) == [
        ("/imageModulesData/0/mainImage/sourceUri/uri", "person.photo")
    ]


def test_a_bound_image_placeholder_produces_one_image_mapping_rule() -> None:
    draft = _draft(
        image_modules=[
            ImageModuleDraft(module_id="photo", uri="person.photo", bound=True)
        ]
    )
    result = build_object(draft, OBJECT_ID, CLASS_ID)

    rules = build_mappings(result, {"person.photo": "image"})["rules"]

    assert len(rules) == 1
    assert rules[0]["source_field"] == "person.photo"
    assert rules[0]["value_type"] == "image"
    assert rules[0]["target"] == "/imageModulesData/0/mainImage/sourceUri/uri"


def test_a_mix_of_bound_and_unbound_image_modules_land_correctly() -> None:
    draft = _draft(
        image_modules=[
            ImageModuleDraft(module_id="photo", uri="person.photo", bound=True),
            ImageModuleDraft(
                module_id="logo", uri="https://example.org/logo.png", bound=False
            ),
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["imageModulesData"]

    assert modules[0]["mainImage"]["sourceUri"]["uri"] == "${person.photo}"
    assert modules[1]["mainImage"]["sourceUri"]["uri"] == "https://example.org/logo.png"
