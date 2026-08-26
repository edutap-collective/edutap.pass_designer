"""Validation catches what Google would swallow in silence."""

from edutap.pass_designer.draft.models import (
    BarcodeSection,
    Cell,
    Draft,
    FieldRef,
    Line,
    Row,
    TextModuleDraft,
)
from edutap.pass_designer.validation import validate

CATALOGUE = {"person.display_name": "text"}


def _text(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="text", module_id=module_id)])


def _draft(**overrides: object) -> Draft:
    base = {
        "family": "loyalty",
        "head": {
            "issuerName": "Example University",
            "programName": "Library",
            # Google's REST reference lists four fields required on create for
            # Loyalty (issuerName, programName, programLogo, reviewStatus);
            # reviewStatus carries a default upstream, so this fixture must
            # supply the other three or every test here would also trip the
            # missing-required-head-field check.
            "programLogo": "https://example.org/logo.png",
        },
    }
    return Draft(**{**base, **overrides})


def test_a_field_path_without_a_module_is_an_error() -> None:
    draft = _draft(front_rows=[Row(cells=[Cell(first=_text("ghost"))])])

    findings = validate(draft, CATALOGUE)

    assert any(f.severity == "error" and "ghost" in f.message for f in findings)


def test_a_resolvable_field_path_produces_nothing() -> None:
    draft = _draft(
        front_rows=[Row(cells=[Cell(first=_text("name"))])],
        text_modules=[TextModuleDraft(module_id="name", value="x")],
    )

    assert [f for f in validate(draft, CATALOGUE) if f.severity == "error"] == []


def test_a_missing_required_head_field_is_an_error() -> None:
    draft = Draft(family="loyalty", head={"issuerName": "Example University"})

    findings = validate(draft, CATALOGUE)

    assert any("programName" in f.message for f in findings)


def test_the_sixth_text_module_produces_a_warning() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(module_id=f"m{index}", value="x") for index in range(6)
        ]
    )

    assert any(
        f.severity == "warning" and "10" in f.message
        for f in validate(draft, CATALOGUE)
    )


def test_the_eleventh_text_module_is_an_error() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(module_id=f"m{index}", value="x") for index in range(11)
        ]
    )

    assert any(
        f.severity == "error" and "10" in f.message for f in validate(draft, CATALOGUE)
    )


def test_a_bound_field_unknown_to_the_catalogue_is_a_warning() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(module_id="x", value="person.nonesuch", bound=True)
        ]
    )

    assert any("person.nonesuch" in f.message for f in validate(draft, CATALOGUE))


def test_a_lone_dollar_sign_in_a_constant_is_an_error() -> None:
    draft = _draft(text_modules=[TextModuleDraft(module_id="fee", value="costs 5$")])

    assert any(
        f.severity == "error" and "$" in f.message for f in validate(draft, CATALOGUE)
    )


def test_a_broken_field_path_in_barcode_first_top_is_an_error() -> None:
    draft = _draft(barcode_section=BarcodeSection(first_top=_text("ghost")))

    findings = validate(draft, CATALOGUE)

    assert any(f.severity == "error" and "ghost" in f.message for f in findings)


def test_a_broken_field_path_in_barcode_second_top_is_an_error() -> None:
    draft = _draft(barcode_section=BarcodeSection(second_top=_text("ghost")))

    findings = validate(draft, CATALOGUE)

    assert any(f.severity == "error" and "ghost" in f.message for f in findings)


def test_a_broken_field_path_in_barcode_first_bottom_is_an_error() -> None:
    draft = _draft(barcode_section=BarcodeSection(first_bottom=_text("ghost")))

    findings = validate(draft, CATALOGUE)

    assert any(f.severity == "error" and "ghost" in f.message for f in findings)


def test_a_resolvable_field_path_in_barcode_first_top_produces_nothing() -> None:
    draft = _draft(
        barcode_section=BarcodeSection(first_top=_text("name")),
        text_modules=[TextModuleDraft(module_id="name", value="x")],
    )

    assert [f for f in validate(draft, CATALOGUE) if f.severity == "error"] == []


def test_a_resolvable_field_path_in_barcode_second_top_produces_nothing() -> None:
    draft = _draft(
        barcode_section=BarcodeSection(second_top=_text("name")),
        text_modules=[TextModuleDraft(module_id="name", value="x")],
    )

    assert [f for f in validate(draft, CATALOGUE) if f.severity == "error"] == []


def test_a_resolvable_field_path_in_barcode_first_bottom_produces_nothing() -> None:
    draft = _draft(
        barcode_section=BarcodeSection(first_bottom=_text("name")),
        text_modules=[TextModuleDraft(module_id="name", value="x")],
    )

    assert [f for f in validate(draft, CATALOGUE) if f.severity == "error"] == []
