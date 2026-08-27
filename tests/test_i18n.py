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
    english = translator("en")
    german = translator("de")
    msgid = "Google requires '%(key)s' when the class is created"

    assert german(msgid) != english(msgid)


def test_an_unknown_message_falls_back_to_its_own_text() -> None:
    german = translator("de")

    assert german("not in any catalogue") == "not in any catalogue"
