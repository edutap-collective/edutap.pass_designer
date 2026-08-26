"""Personas are coherent, reproducible and never real."""

from edutap.pass_designer.personas.catalogue import catalogue_types, load_catalogue
from edutap.pass_designer.personas.generator import FAMILY_NAME_FIRST, build_personas
from edutap.pass_designer.settings import DEFAULT_CATALOGUE_PATH

# Reuses the same repo-root-anchored default `settings.py` resolves for the
# HTTP service, rather than a second, independently bug-prone relative path —
# see that module for why a bare `Path("data/catalogue.example.json")` only
# resolves when the process happens to run from the repository root.
CATALOGUE_PATH = DEFAULT_CATALOGUE_PATH


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


def test_every_persona_is_internally_coherent() -> None:
    """The name parts must be real name parts, not titles or degrees.

    Faker's composed `name_*` providers wrap German and Turkish names in
    academic titles and degree suffixes ("Prof. Liselotte Bien B.Sc."); a
    whitespace split of that string misattributes the suffix as the family
    name. Checking every persona, not just one, is what catches this — a
    single persona can look fine by chance.
    """
    personas = build_personas(load_catalogue(CATALOGUE_PATH))

    for persona in personas:
        given = persona.values["person.given_name"]
        family = persona.values["person.family_name"]
        display = persona.values["person.display_name"]

        assert given, persona.persona_id
        assert family, persona.persona_id
        assert given != family, persona.persona_id
        assert "." not in given, persona.persona_id
        assert "." not in family, persona.persona_id
        assert given in display, persona.persona_id
        assert family in display, persona.persona_id

        if persona.locale in FAMILY_NAME_FIRST:
            assert " " not in display, persona.persona_id
            assert display == f"{family}{given}", persona.persona_id


def test_one_persona_has_deliberately_empty_fields() -> None:
    personas = build_personas(load_catalogue(CATALOGUE_PATH))

    sparse = [p for p in personas if any(value == "" for value in p.values.values())]
    assert sparse, "a sparse persona is the only way to see a fallback chain work"


def test_an_unmapped_field_is_visibly_generic() -> None:
    from edutap.pass_designer.personas.catalogue import CatalogueField

    fields = [CatalogueField(key="odd.thing", value_type="text", label="Odd")]
    persona = build_personas(fields)[0]

    assert persona.values["odd.thing"].startswith("text-")
