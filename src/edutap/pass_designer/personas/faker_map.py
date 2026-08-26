"""Which Faker provider stands behind which catalogue field.

`value_type` alone is not enough — `text` covers a name, a faculty and a job
title equally well. The table is explicit and lives beside the catalogue so a
gap in it shows up in a diff. An unmapped field falls back to something
visibly generic rather than something plausible, so the gap is noticed rather
than believed.
"""

PROVIDER_BY_FIELD: dict[str, str] = {
    "person.given_name": "given_name",
    "person.family_name": "family_name",
    "person.display_name": "display_name",
    "person.date_of_birth": "date_of_birth",
    "person.photo": "photo_uri",
    "affiliation.primary": "affiliation",
    "affiliation.unit": "organisational_unit",
    "card.number": "card_number",
    "card.valid_until": "valid_until",
    "card.homepage": "homepage",
}
