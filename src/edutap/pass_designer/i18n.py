"""Rendering finding messages in the reader's language.

The English sentence is the msgid. A language without a catalogue entry
therefore falls back to English rather than to a key, which means a missing
translation looks unfinished instead of broken.
"""

import gettext
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

#: Languages with a catalogue. Adding one is a catalogue plus an entry here.
SUPPORTED = ("en", "de")
DEFAULT = "en"

_LOCALE_DIR = Path(__file__).resolve().parents[3] / "locales"


def negotiate(accept_language: str | None) -> str:
    """Return the best supported language for an `Accept-Language` header.

    Deliberately simple: quality values order the candidates, and the first
    candidate whose primary subtag we support wins. Anything unrecognised
    yields the default rather than an error — a browser asking for Finnish
    gets English, not a 400.
    """
    if not accept_language:
        return DEFAULT
    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate(accept_language.split(",")):
        tag, _, params = part.strip().partition(";")
        quality = 1.0
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        # `index` keeps the header's own order stable among equal qualities.
        candidates.append((-quality, index, tag.strip().lower()))
    for _, _, tag in sorted(candidates):
        primary = tag.split("-")[0]
        if primary in SUPPORTED:
            return primary
    return DEFAULT


@lru_cache(maxsize=len(SUPPORTED) + 1)
def translator(language: str) -> Callable[[str], str]:
    """Return a gettext function for `language`, cached per process."""
    catalogue = gettext.translation(
        "messages",
        localedir=str(_LOCALE_DIR),
        languages=[language],
        fallback=True,
    )
    return catalogue.gettext
