"""The finding type and the helpers every check shares."""

from collections.abc import Mapping
from typing import Literal

from edutap.wallet_google.models.datatypes.enums import BarcodeType
from pydantic import AnyUrl, BaseModel, TypeAdapter, ValidationError

from ..placeholders import FIELD_KEY_PATTERN, check_dollar_signs, scan

MODULE_LIMIT = 10
MODULE_WARNING_THRESHOLD = 6

Severity = Literal["error", "warning"]

#: The exporter builds `ImageUri(uri=...)`, whose `uri` is a strict `AnyUrl`
#: upstream. Validating with the same adapter means this check and the export
#: cannot disagree about what counts as a URL.
_URL_ADAPTER: TypeAdapter[AnyUrl] = TypeAdapter(AnyUrl)

BARCODE_TYPES = frozenset(member.value for member in BarcodeType)


class Finding(BaseModel):
    """One problem with a draft."""

    severity: Severity
    message: str
    location: str


def is_url(value: str) -> bool:
    """Return True when the exporter would accept `value` as an image URI."""
    try:
        _URL_ADAPTER.validate_python(value)
    except ValidationError:
        return False
    return True


def bindings(text: str) -> list[str]:
    """Return every field key bound inside `text`, in order."""
    return [field_key for _, field_key in scan(text)]


def check_bound_value(
    where: str, value: str, catalogue: Mapping[str, str]
) -> list[Finding]:
    """Check a value the designer marked as bound to a provider field."""
    if not value:
        return [
            Finding(
                severity="error",
                location=where,
                message=(
                    "is marked as bound but names no field; it would export as "
                    "'${}', import back as constant text, and then fail to "
                    "export again"
                ),
            )
        ]
    if not FIELD_KEY_PATTERN.match(value):
        return [
            Finding(
                severity="error",
                location=where,
                message=(
                    f"'{value}' is not a field key; a binding is a dotted "
                    f"identifier such as 'person.display_name'"
                ),
            )
        ]
    if value not in catalogue:
        return [
            Finding(
                severity="warning",
                location=where,
                message=(
                    f"'{value}' is not in the field catalogue; the pass builder "
                    f"will not be able to fill it"
                ),
            )
        ]
    return []


def check_constant(where: str, value: str) -> list[Finding]:
    """Check a value that is written through to Google unchanged."""
    return [
        Finding(severity="error", location=where, message=problem)
        for problem in check_dollar_signs(value)
    ]
