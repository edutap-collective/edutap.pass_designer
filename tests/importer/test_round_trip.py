"""Importing what was exported must give back the same design.

`ORIGINAL` deliberately exercises every shape that broke, or nearly broke,
during Tasks 5 and 6: a three-cell front row, a two-reference fallback
chain, a cell using both `first` and `second`, an image reference inside a
row, a barcode section slot, back items, both list rows, an image head
field, an object-scoped head field, a bound image module, an unbound image
module, a bound text module, a constant text module, link modules, and
smart tap. A round trip that only exercises plain text is not a round trip
test — it is a test that the happy path is happy.
"""

from typing import Any

from edutap.pass_designer.draft.models import (
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
from edutap.pass_designer.exporter.class_json import build_class
from edutap.pass_designer.exporter.object_json import build_object
from edutap.pass_designer.importer.reader import read

CLASS_ID = "3388000000000000000.library.demo"
OBJECT_ID = "3388000000000000000.specimen.object"


def _text(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="text", module_id=module_id)])


def _image(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="image", module_id=module_id)])


ORIGINAL = Draft(
    family="loyalty",
    head={
        "issuerName": "Example University",
        "programName": "Library",
        # Image head field (Ruling B on the export side): must round-trip as
        # a plain string, not stay wrapped as {"sourceUri": {"uri": ...}}.
        "programLogo": "https://example.org/logo.png",
        # Object-scoped head field (Ruling A): lives on the object, not the
        # class, and must be read back from the right document.
        "accountId": "A-12345",
    },
    front_rows=[
        Row(
            cells=[
                # A two-reference fallback chain.
                Cell(
                    first=Line(
                        fallback_chain=[
                            FieldRef(kind="text", module_id="staff_id"),
                            FieldRef(kind="text", module_id="student_id"),
                        ]
                    )
                ),
                # An image reference inside a row.
                Cell(first=_image("photo")),
                # A cell using both `first` and `second`.
                Cell(first=_text("name"), second=_text("card_no")),
            ]
        )
    ],
    barcode_section=BarcodeSection(first_bottom=_text("hint")),
    back_items=[Cell(first=_text("group"))],
    list_view=ListView(first_row=_text("name"), second_row=_text("card_no")),
    text_modules=[
        TextModuleDraft(
            module_id="name", header="Name", value="person.display_name", bound=True
        ),
        TextModuleDraft(module_id="card_no", header="Card number", value="42"),
        TextModuleDraft(module_id="group", header="Group", value="Staff"),
        TextModuleDraft(module_id="staff_id", header="Staff ID", value="staff.id"),
        TextModuleDraft(module_id="student_id", header="Student ID", value=""),
        TextModuleDraft(module_id="hint", header="Hint", value="Scan at the desk"),
    ],
    image_modules=[
        # Bound image module.
        ImageModuleDraft(module_id="photo", uri="person.photo", bound=True),
        # Unbound image module.
        ImageModuleDraft(
            module_id="stamp", uri="https://example.org/stamp.png", bound=False
        ),
    ],
    link_modules=[
        LinkModuleDraft(uri="https://example.org/help", description="Help"),
        LinkModuleDraft(uri="https://example.org/terms"),
    ],
    redemption=RedemptionSettings(
        smart_tap_enabled=True,
        redemption_issuers=["3388000000000000000"],
        redemption_value="LIBRARY-CARD",
    ),
)


def _round_trip() -> tuple[dict[str, Any], dict[str, Any], Draft]:
    class_json = build_class(ORIGINAL, CLASS_ID)
    object_json = build_object(ORIGINAL, OBJECT_ID, CLASS_ID)
    restored = read(class_json, object_json, family="loyalty")
    return class_json, object_json, restored


def test_a_design_survives_export_and_import() -> None:
    """Every field the editor actually edits must come back unchanged.

    `unmapped` is excluded on purpose: exporting `ORIGINAL` — whose own
    `unmapped` is empty — still produces a `class_json`/`object_json` that
    carries the upstream model's own defaults (e.g. `reviewStatus`,
    `notifyPreference`), because a full `model_dump` always reports a value
    for every field with a non-None default. Reading those documents back
    necessarily buckets those defaults into `restored.unmapped`, which
    `ORIGINAL.unmapped` never had anything in. That is not data loss — it is
    the mechanism working as designed, and
    `test_a_second_export_is_identical_to_the_first` below proves it by
    checking what actually matters: that exporting the restored draft
    reproduces the same documents byte for byte.
    """
    _, _, restored = _round_trip()

    assert restored.family == ORIGINAL.family
    assert restored.head == ORIGINAL.head
    assert restored.front_rows == ORIGINAL.front_rows
    assert restored.barcode_section == ORIGINAL.barcode_section
    assert restored.back_items == ORIGINAL.back_items
    assert restored.list_view == ORIGINAL.list_view
    assert restored.text_modules == ORIGINAL.text_modules
    assert restored.image_modules == ORIGINAL.image_modules
    assert restored.link_modules == ORIGINAL.link_modules
    assert restored.redemption == ORIGINAL.redemption


def test_a_second_export_is_identical_to_the_first() -> None:
    """The real test of `unmapped`: re-exporting must reproduce the same JSON.

    This is what "open and save" fidelity actually means. `restored.unmapped`
    differing in *shape* from `ORIGINAL.unmapped` (empty dict vs the model's
    own defaults) is fine as long as it makes `build_class`/`build_object`
    produce the exact same documents on the next export.
    """
    class_json, object_json, restored = _round_trip()

    assert build_class(restored, CLASS_ID) == class_json
    assert build_object(restored, OBJECT_ID, CLASS_ID) == object_json


def test_a_placeholder_comes_back_as_a_bound_value() -> None:
    _, object_json, restored = _round_trip()
    name = next(m for m in restored.text_modules if m.module_id == "name")

    assert name.bound is True
    assert name.value == "person.display_name"
    assert object_json["textModulesData"] is not None


def test_a_bound_image_module_comes_back_as_a_bound_value() -> None:
    _, _, restored = _round_trip()
    photo = next(m for m in restored.image_modules if m.module_id == "photo")

    assert photo.bound is True
    assert photo.uri == "person.photo"


def test_an_unbound_image_module_keeps_its_uri() -> None:
    _, _, restored = _round_trip()
    stamp = next(m for m in restored.image_modules if m.module_id == "stamp")

    assert stamp.bound is False
    assert stamp.uri == "https://example.org/stamp.png"


def test_an_image_head_field_is_unwrapped_back_to_a_plain_string() -> None:
    _, _, restored = _round_trip()

    assert restored.head["programLogo"] == "https://example.org/logo.png"


def test_an_object_scoped_head_field_is_read_from_the_object() -> None:
    _, _, restored = _round_trip()

    assert restored.head["accountId"] == "A-12345"


def test_unrecognised_fields_are_kept_and_written_back() -> None:
    class_json = {
        **build_class(ORIGINAL, CLASS_ID),
        "securityAnimation": {"animationType": "FOIL_SHIMMER"},
    }

    restored = read(
        class_json, build_object(ORIGINAL, OBJECT_ID, CLASS_ID), family="loyalty"
    )
    again = build_class(restored, CLASS_ID)

    assert again["securityAnimation"] == {"animationType": "FOIL_SHIMMER"}
