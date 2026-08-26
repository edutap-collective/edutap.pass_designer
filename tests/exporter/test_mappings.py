"""Mapping rules are derived from the placeholders that were written."""

from edutap.pass_designer.exporter.mappings import build_mappings

CATALOGUE = {"person.display_name": "text", "person.photo": "image"}


def test_every_placeholder_produces_a_rule() -> None:
    object_json = {
        "textModulesData": [{"id": "name", "body": "${person.display_name}"}]
    }

    rules = build_mappings(object_json, CATALOGUE)["rules"]

    assert len(rules) == 1
    assert rules[0]["source_field"] == "person.display_name"
    assert rules[0]["target"] == "/textModulesData/0/body"
    assert rules[0]["target_kind"] == "json_pointer"
    assert rules[0]["value_type"] == "text"


def test_the_value_type_comes_from_the_catalogue() -> None:
    object_json = {
        "imageModulesData": [
            {"id": "photo", "mainImage": {"sourceUri": {"uri": "${person.photo}"}}}
        ]
    }

    rules = build_mappings(object_json, CATALOGUE)["rules"]

    assert rules[0]["value_type"] == "image"


def test_a_field_missing_from_the_catalogue_defaults_to_text_and_is_flagged() -> None:
    object_json = {"textModulesData": [{"id": "x", "body": "${person.unknown}"}]}

    result = build_mappings(object_json, CATALOGUE)

    assert result["rules"][0]["value_type"] == "text"
    assert "person.unknown" in result["unknown_fields"]


def test_constants_produce_no_rules() -> None:
    object_json = {"textModulesData": [{"id": "issuer", "body": "A constant"}]}

    assert build_mappings(object_json, CATALOGUE)["rules"] == []
