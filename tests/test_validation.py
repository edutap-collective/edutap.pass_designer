"""Validation catches what Google would swallow in silence."""

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
    TransitOption,
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


# ---------------------------------------------------------------------------
# Issue #4 -- the validator must predict what the exporter refuses.
#
# Each of these drafts used to pass validation with zero errors and then fail
# the export. `/validate` is what a live editor calls on every keystroke;
# `/export` is what a person presses once at the end. A designer must not spend
# a session watching a green validator and only then learn the draft was never
# valid.
# ---------------------------------------------------------------------------


def _errors(draft: Draft) -> list[str]:
    return [f.message for f in validate(draft, CATALOGUE) if f.severity == "error"]


def test_a_transit_option_in_the_list_view_is_reported() -> None:
    draft = _draft(list_view=ListView(first_row=TransitOption(option="ORIGIN_NAME")))

    assert any("transit" in message.lower() for message in _errors(draft))


def test_an_image_head_field_that_is_not_a_url_is_reported() -> None:
    draft = _draft(head={**_draft().head, "programLogo": "not a url"})

    assert any("programLogo" in message for message in _errors(draft))


def test_a_well_formed_image_head_field_is_accepted() -> None:
    assert _errors(_draft()) == []


def test_a_barcode_type_google_does_not_know_is_reported() -> None:
    draft = _draft(redemption=RedemptionSettings(barcode_type="NOT_A_TYPE"))

    assert any("NOT_A_TYPE" in message for message in _errors(draft))


def test_a_barcode_type_google_knows_is_accepted() -> None:
    draft = _draft(
        redemption=RedemptionSettings(barcode_type="AZTEC", barcode_value="x")
    )

    assert _errors(draft) == []


def test_an_unbound_image_module_uri_that_is_not_a_url_is_reported() -> None:
    draft = _draft(image_modules=[ImageModuleDraft(module_id="photo", uri="not a uri")])

    assert any("photo" in message for message in _errors(draft))


# ---------------------------------------------------------------------------
# Issue #3 -- placeholder syntax on every surface that can carry text.
#
# The design says flatly that the export refuses a lone `$`. It used to refuse
# it in one place out of six.
# ---------------------------------------------------------------------------


def test_a_lone_dollar_sign_is_reported_in_a_head_field() -> None:
    draft = _draft(head={**_draft().head, "issuerName": "Cost is 5$ per year"})

    assert any("$" in message for message in _errors(draft))


def test_a_lone_dollar_sign_is_reported_in_a_link() -> None:
    draft = _draft(
        link_modules=[LinkModuleDraft(uri="https://example.org/", description="pay $5")]
    )

    assert any("$" in message for message in _errors(draft))


def test_a_lone_dollar_sign_is_reported_in_the_barcode_value() -> None:
    draft = _draft(
        redemption=RedemptionSettings(barcode_type="AZTEC", barcode_value="raw$value")
    )

    assert any("$" in message for message in _errors(draft))


def test_a_lone_dollar_sign_is_reported_in_the_smart_tap_value() -> None:
    draft = _draft(redemption=RedemptionSettings(redemption_value="Fee: $9"))

    assert any("$" in message for message in _errors(draft))


def test_a_bound_value_that_is_empty_is_reported() -> None:
    # Exports as "${}", imports back as a CONSTANT, and the re-export then
    # fails. The tool would write a file it cannot reopen.
    draft = _draft(
        text_modules=[TextModuleDraft(module_id="name", value="", bound=True)]
    )

    assert _errors(draft) != []


def test_a_bound_value_that_is_not_a_field_key_is_reported() -> None:
    draft = _draft(
        text_modules=[TextModuleDraft(module_id="name", value="foo}bar", bound=True)]
    )

    assert any("foo}bar" in message for message in _errors(draft))


def test_a_bound_image_module_that_is_empty_is_reported() -> None:
    draft = _draft(
        image_modules=[ImageModuleDraft(module_id="photo", uri="", bound=True)]
    )

    assert _errors(draft) != []


def test_a_placeholder_in_a_class_scoped_head_field_is_reported() -> None:
    # The class IS the template: one class serves every pass, so a per-person
    # value has no place in it. Without this the export ships the literal text
    # and the cardholder sees "${affiliation.primary}" as the issuer.
    draft = _draft(head={**_draft().head, "issuerName": "${affiliation.primary}"})

    messages = _errors(draft)
    assert any("issuerName" in message for message in messages)
    assert any("template" in message.lower() for message in messages)


def test_a_placeholder_in_an_object_scoped_head_field_is_allowed() -> None:
    # accountId lives on the object, differs per person, and already gets a
    # mapping rule because build_mappings scans the object.
    draft = _draft(head={**_draft().head, "accountId": "${person.display_name}"})

    assert _errors(draft) == []


def test_a_bound_head_field_unknown_to_the_catalogue_warns() -> None:
    draft = _draft(head={**_draft().head, "accountId": "${person.nonesuch}"})

    warnings = [
        f.message for f in validate(draft, CATALOGUE) if f.severity == "warning"
    ]
    assert any("person.nonesuch" in message for message in warnings)


# ---------------------------------------------------------------------------
# `language` decides only how the messages read; which findings exist does
# not depend on it — see `validate`'s docstring.
# ---------------------------------------------------------------------------


def test_the_language_argument_changes_the_message_text() -> None:
    draft = Draft(family="loyalty", head={"issuerName": "Example University"})

    english = validate(draft, CATALOGUE, language="en")
    german = validate(draft, CATALOGUE, language="de")

    assert [f.message for f in english] != [f.message for f in german]
    assert [(f.severity, f.location) for f in english] == [
        (f.severity, f.location) for f in german
    ]


def test_an_unsupported_language_falls_back_to_english() -> None:
    draft = Draft(family="loyalty", head={"issuerName": "Example University"})

    findings = validate(draft, CATALOGUE, language="fr")

    assert findings == validate(draft, CATALOGUE, language="en")
