"""Checks the Pydantic models cannot make.

The most important one is in `layout`. Google discards a `fieldPath` that
refers to a module the object does not carry — silently. The row simply does
not appear, with no error at any layer, which makes it the one defect that
cannot be found by looking at either side alone.

`exportable` is the second half of that idea, pointed at ourselves: without
it a draft passes validation and then fails the export, and the two halves of
this package would disagree about what a valid draft is.
"""

from collections.abc import Mapping

from ..draft.models import Draft
from ..i18n import DEFAULT, translator
from ._common import MODULE_LIMIT, MODULE_WARNING_THRESHOLD, Finding, Severity
from .exportable import check_exportable
from .layout import (
    check_duplicate_module_ids,
    check_field_paths,
    check_required_head_fields,
    check_volume,
)
from .values import check_values

__all__ = [
    "MODULE_LIMIT",
    "MODULE_WARNING_THRESHOLD",
    "Finding",
    "Severity",
    "validate",
]


def validate(
    draft: Draft, catalogue: Mapping[str, str], language: str = DEFAULT
) -> list[Finding]:
    """Return every problem found, errors and warnings together.

    `language` decides only how the messages read; which findings exist does
    not depend on it.
    """
    templates = [
        *check_field_paths(draft),
        *check_duplicate_module_ids(draft),
        *check_required_head_fields(draft),
        *check_volume(draft),
        *check_values(draft, catalogue),
        *check_exportable(draft),
    ]
    translate = translator(language)
    return [template.render(translate) for template in templates]
