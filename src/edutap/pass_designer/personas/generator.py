"""Build coherent, reproducible preview personas.

A persona draws its locale and gender once and derives everything else from
them, so the person has a name, a birth date and an affiliation that belong
together. Drawing each field independently would produce a name from one
country and a birthplace from another, and the preview would be useless for
judging a layout.

The seed is fixed so that comparing two layouts is not confounded by a
changing name.

Given and family names are drawn from Faker's dedicated part providers
(`first_name_*` / `last_name_*`), not by splitting a composed `name_*`
string: `name_*` routinely wraps the name in academic titles and degree
suffixes for `de_DE` and `tr_TR` ("Prof. Liselotte Bien B.Sc."), and a
whitespace split then misattributes the suffix as the family name. All six
part providers were checked to resolve on a single-locale `Faker` instance
for all five locales below (Faker 40.37.0) before this table was trusted —
see the task report for the per-locale results. A locale missing a provider
would be dropped rather than falling back to a composed name or a different
gender's provider — a persona that lies about its own gender or borrows
someone else's name part is worse than one locale fewer.
"""

from collections.abc import Iterable, Sequence

from faker import Faker
from pydantic import BaseModel

from .catalogue import CatalogueField
from .faker_map import PROVIDER_BY_FIELD

SEED = 20260826

#: (identifier, label, locale, gender, sparse)
PERSONA_RECIPES: Sequence[tuple[str, str, str, str, bool]] = (
    ("de-female", "German, female", "de_DE", "female", False),
    ("en-male", "English, male", "en_US", "male", False),
    ("fr-nonbinary", "French, non-binary", "fr_FR", "non-binary", False),
    ("tr-female", "Turkish, female", "tr_TR", "female", False),
    ("zh-male", "Chinese, male", "zh_CN", "male", False),
    ("sparse", "Sparse — many fields empty", "de_DE", "non-binary", True),
)

#: Fields a sparse persona deliberately leaves empty, so that a fallback
#: chain has something to fall back from.
_SPARSE_EMPTY = {"person.date_of_birth", "affiliation.unit", "card.valid_until"}

#: Locales whose convention puts the family name first, with no separator
#: (Chinese: 姓 before 名, joined directly). `_compose_display_name` uses
#: this instead of the Western `given family` order.
FAMILY_NAME_FIRST = frozenset({"zh_CN"})


class Persona(BaseModel):
    """One preview person: coherent, fictional, reproducible."""

    persona_id: str
    label: str
    locale: str
    gender: str
    values: dict[str, str]


def _name(faker: Faker, gender: str) -> tuple[str, str]:
    """Return `(given, family)` for the persona's gender.

    Drawn from Faker's dedicated part providers, never from splitting a
    composed `name_*` string — see the module docstring for why.
    """
    if gender == "female":
        return faker.first_name_female(), faker.last_name_female()
    if gender == "male":
        return faker.first_name_male(), faker.last_name_male()
    return faker.first_name_nonbinary(), faker.last_name_nonbinary()


def _compose_display_name(locale: str, given: str, family: str) -> str:
    """Join given and family name by locale convention."""
    if locale in FAMILY_NAME_FIRST:
        return f"{family}{given}"
    return f"{given} {family}"


def _value(
    faker: Faker,
    provider: str | None,
    field: CatalogueField,
    given: str,
    family: str,
    display_name: str,
) -> str:
    if provider == "given_name":
        return given
    if provider == "family_name":
        return family
    if provider == "display_name":
        return display_name
    if provider == "date_of_birth":
        return faker.date_of_birth(minimum_age=18, maximum_age=70).strftime("%d.%m.%Y")
    if provider == "photo_uri":
        return "https://example.org/photo/specimen.png"
    if provider == "affiliation":
        return faker.random_element(["student", "staff", "member"])
    if provider == "organisational_unit":
        return faker.random_element(
            ["Central Library", "IT Services", "Faculty Office"]
        )
    if provider == "card_number":
        return faker.numerify("############")
    if provider == "valid_until":
        return faker.date_between(start_date="+180d", end_date="+900d").strftime(
            "%d.%m.%Y"
        )
    if provider == "homepage":
        return "https://example.org/"
    # Deliberately not plausible: a gap in the table must look like a gap.
    return f"{field.value_type}-{faker.numerify('####')}"


def build_personas(fields: Iterable[CatalogueField]) -> list[Persona]:
    """Return one persona per recipe, each filling every catalogue field."""
    catalogue = list(fields)
    personas: list[Persona] = []
    for offset, (persona_id, label, locale, gender, sparse) in enumerate(
        PERSONA_RECIPES
    ):
        faker = Faker(locale)
        faker.seed_instance(SEED + offset)
        given, family = _name(faker, gender)
        display_name = _compose_display_name(locale, given, family)
        values: dict[str, str] = {}
        for field in catalogue:
            if sparse and field.key in _SPARSE_EMPTY:
                values[field.key] = ""
                continue
            values[field.key] = _value(
                faker,
                PROVIDER_BY_FIELD.get(field.key),
                field,
                given,
                family,
                display_name,
            )
        personas.append(
            Persona(
                persona_id=persona_id,
                label=label,
                locale=locale,
                gender=gender,
                values=values,
            )
        )
    return personas
