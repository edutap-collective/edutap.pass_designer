"""Placeholders follow the manager's syntax exactly."""

from edutap.pass_designer.placeholders import (
    check_dollar_signs,
    is_placeholder,
    placeholder_for,
    resolve,
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
    msgid, params = problems[0]
    assert params["position"] == 7
    assert params["text"] == "costs 5$"
    assert msgid % params == (
        "lone '$' at position 7 in 'costs 5$': write '$$' for a literal dollar sign"
    )


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


def test_malformed_placeholder_with_nested_dollar() -> None:
    problems = check_dollar_signs("${bad ${good}")

    assert len(problems) == 1
    msgid, params = problems[0]
    assert params["field_key"] == "bad ${good"
    assert "malformed" in msgid.lower()


def test_malformed_placeholder_with_dollar_in_key() -> None:
    problems = check_dollar_signs("${a$b}")

    assert len(problems) == 1
    _, params = problems[0]
    assert params["field_key"] == "a$b"


def test_single_segment_field_key_is_valid() -> None:
    problems = check_dollar_signs("${card}")

    assert problems == []


def test_dotted_field_key_is_valid() -> None:
    problems = check_dollar_signs("${person.display_name}")

    assert problems == []


def test_resolve_substitutes_placeholders_in_strings() -> None:
    result = resolve("Hello ${person.name}", {"person.name": "Alice"})

    assert result == "Hello Alice"


def test_resolve_leaves_unknown_keys_untouched() -> None:
    result = resolve("Hello ${person.name}", {"other.field": "Bob"})

    assert result == "Hello ${person.name}"


def test_resolve_converts_doubled_dollar_to_literal() -> None:
    result = resolve("costs 5$$", {})

    assert result == "costs 5$"


def test_resolve_works_in_nested_structures() -> None:
    document = {
        "textModulesData": [
            {"body": "${person.display_name}"},
            {"body": "A constant"},
        ]
    }
    values = {"person.display_name": "Ludwig Maximilian"}

    result = resolve(document, values)

    assert result == {
        "textModulesData": [
            {"body": "Ludwig Maximilian"},
            {"body": "A constant"},
        ]
    }


def test_resolve_never_substitutes_dictionary_keys() -> None:
    document = {"${person.name}": "value"}
    values = {"person.name": "Alice"}

    result = resolve(document, values)

    assert result == {"${person.name}": "value"}
