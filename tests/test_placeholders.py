"""Placeholders follow the manager's syntax exactly."""

from edutap.pass_designer.placeholders import (
    check_dollar_signs,
    is_placeholder,
    placeholder_for,
    scan,
    source_field,
)


def test_a_placeholder_wraps_a_dotted_field_key() -> None:
    assert placeholder_for("person.display_name") == "${person.display_name}"


def test_a_placeholder_is_recognised_and_its_field_extracted() -> None:
    assert is_placeholder("${person.display_name}")
    assert source_field("${person.display_name}") == "person.display_name"


def test_constant_text_is_not_a_placeholder() -> None:
    assert not is_placeholder("Ludwig-Maximilians-Universitat Munchen")
    assert source_field("plain text") is None


def test_a_doubled_dollar_sign_is_literal_and_allowed() -> None:
    assert check_dollar_signs("costs 5$$") == []


def test_a_lone_dollar_sign_is_reported() -> None:
    problems = check_dollar_signs("costs 5$")

    assert len(problems) == 1
    assert "$" in problems[0]


def test_scan_reports_a_json_pointer_for_every_placeholder() -> None:
    document = {
        "textModulesData": [
            {"id": "name", "body": "${person.display_name}"},
            {"id": "issuer", "body": "A constant"},
        ]
    }

    assert scan(document) == [
        ("/textModulesData/0/body", "person.display_name"),
    ]


def test_scan_ignores_dictionary_keys() -> None:
    assert scan({"${not.a.field}": "value"}) == []
