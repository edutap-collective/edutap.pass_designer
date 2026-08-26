"""Personas are coherent, reproducible and never real."""

from pathlib import Path

from edutap.pass_designer.personas.catalogue import catalogue_types, load_catalogue
from edutap.pass_designer.personas.generator import build_personas

CATALOGUE_PATH = Path("data/catalogue.example.json")


def test_the_example_catalogue_loads() -> None:
    fields = load_catalogue(CATALOGUE_PATH)

    assert any(field.key == "person.display_name" for field in fields)
    assert catalogue_types(fields)["person.date_of_birth"] == "date"


def test_the_three_genders_are_represented() -> None:
    personas = build_personas(load_catalogue(CATALOGUE_PATH))

    assert {persona.gender for persona in personas} >= {"female", "male", "non-binary"}


def test_generation_is_reproducible() -> None:
    fields = load_catalogue(CATALOGUE_PATH)

    first = build_personas(fields)
    second = build_personas(fields)

    assert [p.values for p in first] == [p.values for p in second]


def test_a_persona_is_internally_coherent() -> None:
    persona = build_personas(load_catalogue(CATALOGUE_PATH))[0]

    assert persona.values["person.display_name"].startswith(
        persona.values["person.given_name"]
    )
    assert persona.values["person.family_name"] in persona.values["person.display_name"]


def test_one_persona_has_deliberately_empty_fields() -> None:
    personas = build_personas(load_catalogue(CATALOGUE_PATH))

    sparse = [p for p in personas if any(value == "" for value in p.values.values())]
    assert sparse, "a sparse persona is the only way to see a fallback chain work"


def test_an_unmapped_field_is_visibly_generic() -> None:
    from edutap.pass_designer.personas.catalogue import CatalogueField

    fields = [CatalogueField(key="odd.thing", value_type="text", label="Odd")]
    persona = build_personas(fields)[0]

    assert persona.values["odd.thing"].startswith("text-")
