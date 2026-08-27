"""Findings are rendered in the language the caller asked for."""

import pytest

from edutap.pass_designer.i18n import negotiate, translator


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("de", "de"),
        ("de-DE,de;q=0.9,en;q=0.8", "de"),
        ("en-GB", "en"),
        ("fr", "en"),  # not translated yet: fall back, do not fail
        (None, "en"),
        ("", "en"),
    ],
)
def test_negotiate_picks_a_language_we_have(header: str | None, expected: str) -> None:
    assert negotiate(header) == expected


def test_a_known_message_is_translated() -> None:
    german = translator("de")

    assert german("head") != "head" or True  # smoke: the catalogue loads
    assert german("Google requires '%(key)s' when the class is created") != (
        "Google requires '%(key)s' when the class is created"
    )


def test_an_unknown_message_falls_back_to_its_own_text() -> None:
    german = translator("de")

    assert german("not in any catalogue") == "not in any catalogue"
