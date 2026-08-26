"""The class JSON carries the layout of all three views."""

import pytest

from edutap.pass_designer.draft.models import (
    BarcodeSection,
    Cell,
    Draft,
    FieldRef,
    Line,
    ListView,
    RedemptionSettings,
    Row,
    TransitOption,
)
from edutap.pass_designer.exporter.class_json import build_class

CLASS_ID = "3388000000022141777.library.demo"


def _text(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="text", module_id=module_id)])


def _image(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="image", module_id=module_id)])


def _draft(**overrides: object) -> Draft:
    base = {
        "family": "loyalty",
        "head": {"issuerName": "Example University", "programName": "Library"},
    }
    return Draft(**{**base, **overrides})


def test_a_two_cell_row_becomes_two_items() -> None:
    draft = _draft(
        front_rows=[Row(cells=[Cell(first=_text("name")), Cell(first=_image("photo"))])]
    )

    rows = build_class(draft, CLASS_ID)["classTemplateInfo"]["cardTemplateOverride"][
        "cardRowTemplateInfos"
    ]

    assert "twoItems" in rows[0]
    start = rows[0]["twoItems"]["startItem"]["firstValue"]["fields"]
    end = rows[0]["twoItems"]["endItem"]["firstValue"]["fields"]
    assert start[0]["fieldPath"] == "object.textModulesData['name']"
    assert end[0]["fieldPath"] == "object.imageModulesData['photo']"


def test_a_fallback_chain_becomes_several_field_references() -> None:
    line = Line(
        fallback_chain=[
            FieldRef(kind="text", module_id="staff_id"),
            FieldRef(kind="text", module_id="student_id"),
        ]
    )
    draft = _draft(front_rows=[Row(cells=[Cell(first=line)])])

    rows = build_class(draft, CLASS_ID)["classTemplateInfo"]["cardTemplateOverride"][
        "cardRowTemplateInfos"
    ]
    fields = rows[0]["oneItem"]["item"]["firstValue"]["fields"]

    assert [field["fieldPath"] for field in fields] == [
        "object.textModulesData['staff_id']",
        "object.textModulesData['student_id']",
    ]


def test_the_back_is_a_flat_list_of_single_items() -> None:
    draft = _draft(back_items=[Cell(first=_text("a")), Cell(first=_text("b"))])

    details = build_class(draft, CLASS_ID)["classTemplateInfo"][
        "detailsTemplateOverride"
    ]["detailsItemInfos"]

    assert len(details) == 2
    assert "item" in details[0]
    assert "twoItems" not in details[0]


def test_the_list_view_carries_two_rows_and_no_third() -> None:
    draft = _draft(list_view=ListView(first_row=_text("a"), second_row=_text("b")))

    list_override = build_class(draft, CLASS_ID)["classTemplateInfo"][
        "listTemplateOverride"
    ]

    assert "firstRowOption" in list_override
    assert "secondRowOption" in list_override
    assert "thirdRowOption" not in list_override


def test_the_barcode_section_belongs_to_the_front() -> None:
    draft = _draft(barcode_section=BarcodeSection(first_bottom=_text("hint")))

    section = build_class(draft, CLASS_ID)["classTemplateInfo"][
        "cardBarcodeSectionDetails"
    ]

    assert (
        section["firstBottomDetail"]["fieldSelector"]["fields"][0]["fieldPath"]
        == "object.textModulesData['hint']"
    )
    assert "firstTopDetail" not in section


def test_smart_tap_settings_land_on_the_class() -> None:
    draft = _draft(
        redemption=RedemptionSettings(
            smart_tap_enabled=True, redemption_issuers=["3388000000022141777"]
        )
    )

    result = build_class(draft, CLASS_ID)

    assert result["enableSmartTap"] is True
    assert result["redemptionIssuers"] == ["3388000000022141777"]


def test_head_fields_are_written_through() -> None:
    result = build_class(_draft(), CLASS_ID)

    assert result["issuerName"] == "Example University"
    assert result["programName"] == "Library"
    assert result["id"] == CLASS_ID


# --- Ruling A: head fields are scoped; only "class"-scoped keys reach the class. ---


def test_an_object_scoped_head_field_is_not_written_to_the_class() -> None:
    """`accountName` is scoped to `LoyaltyObject`; `LoyaltyClass` would reject it."""
    draft = _draft(head={"issuerName": "Example University", "accountName": "Jane Doe"})

    result = build_class(draft, CLASS_ID)

    assert "accountName" not in result


def test_a_head_key_the_descriptor_does_not_declare_is_ignored() -> None:
    """An unknown key in `draft.head` is dropped rather than passed through."""
    draft = _draft(
        head={
            "issuerName": "Example University",
            "programName": "Library",
            "notAFamilyField": "should not appear",
        }
    )

    result = build_class(draft, CLASS_ID)

    assert "notAFamilyField" not in result


# --- Ruling B: image head fields are wrapped as `Image(sourceUri=ImageUri(...))` ---


def test_an_image_head_field_is_wrapped_as_a_nested_image() -> None:
    draft = _draft(
        head={
            "issuerName": "Example University",
            "programName": "Library",
            "programLogo": "https://example.org/logo.png",
        }
    )

    result = build_class(draft, CLASS_ID)

    assert result["programLogo"]["sourceUri"]["uri"] == "https://example.org/logo.png"
    assert isinstance(result["programLogo"]["sourceUri"]["uri"], str)


def test_an_empty_image_head_field_is_not_written_to_the_class() -> None:
    draft = _draft(
        head={
            "issuerName": "Example University",
            "programName": "Library",
            "heroImage": "",
        }
    )

    result = build_class(draft, CLASS_ID)

    assert "heroImage" not in result


# --- Ruling C: transit is not in this plan; a TransitOption in the list view raises ---


def test_a_transit_option_in_the_list_view_raises() -> None:
    draft = _draft(list_view=ListView(first_row=TransitOption(option="rideStatus")))

    with pytest.raises(NotImplementedError):
        build_class(draft, CLASS_ID)
