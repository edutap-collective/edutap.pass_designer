"""Resolve and inspect `${field}` placeholders.

The syntax is the one `edutap.pass_builder` applies at issuing time:
`${dotted.field}` is a binding, `$$` is a literal dollar sign, and only string
values are ever touched — never dictionary keys. No filters, no expressions.
"""

import re
from collections.abc import Mapping
from typing import Any

PLACEHOLDER_PATTERN = re.compile(r"\$\$|\$\{([^}]+)\}")
_FULL_PLACEHOLDER = re.compile(r"^\$\{([^}]+)\}$")


def placeholder_for(field_key: str) -> str:
    """Return the placeholder that binds a value to `field_key`."""
    return f"${{{field_key}}}"


def is_placeholder(text: str) -> bool:
    """Return True when `text` is exactly one placeholder and nothing else."""
    return _FULL_PLACEHOLDER.match(text) is not None


def source_field(text: str) -> str | None:
    """Return the field key `text` binds to, or None when it binds nothing."""
    match = _FULL_PLACEHOLDER.match(text)
    return match.group(1) if match else None


def check_dollar_signs(text: str) -> list[str]:
    """Return a problem for every dollar sign that is neither `$$` nor `${`.

    A lone dollar sign is the mistake that survives every other check and
    reaches the cardholder as a literal `$`.
    """
    problems: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "$":
            index += 1
            continue
        remainder = text[index:]
        if remainder.startswith("$$"):
            index += 2
            continue
        match = PLACEHOLDER_PATTERN.match(remainder)
        if match is not None:
            index += match.end()
            continue
        problems.append(
            f"lone '$' at position {index} in {text!r}: "
            f"write '$$' for a literal dollar sign"
        )
        index += 1
    return problems


def _escape(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _walk(obj: Any, pointer: str, out: list[tuple[str, str]]) -> None:
    if isinstance(obj, str):
        for match in PLACEHOLDER_PATTERN.finditer(obj):
            if match.group(1) is not None:
                out.append((pointer, match.group(1)))
    elif isinstance(obj, Mapping):
        for key, value in obj.items():
            _walk(value, f"{pointer}/{_escape(str(key))}", out)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            _walk(value, f"{pointer}/{index}", out)


def scan(obj: Any) -> list[tuple[str, str]]:
    """Return `(json_pointer, source_field)` for every placeholder found."""
    out: list[tuple[str, str]] = []
    _walk(obj, "", out)
    return out


def resolve(obj: Any, values: Mapping[str, str]) -> Any:
    """Return a deep copy with placeholders replaced from `values`."""
    if isinstance(obj, str):

        def replace(match: re.Match[str]) -> str:
            if match.group(0) == "$$":
                return "$"
            return values.get(match.group(1), match.group(0))

        return PLACEHOLDER_PATTERN.sub(replace, obj)
    if isinstance(obj, Mapping):
        return {key: resolve(value, values) for key, value in obj.items()}
    if isinstance(obj, list):
        return [resolve(value, values) for value in obj]
    return obj
