"""Family descriptors: the only place one pass family differs from another.

A descriptor is code rather than data so that it is typed and refactorable,
and it lives on the server so that the form the browser builds and the export
the server validates cannot drift apart.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

HeadFieldKind = Literal["text", "localized_text", "image_uri", "colour", "enum"]


class HeadField(BaseModel):
    """One field of a family's head section."""

    key: str
    label: str
    kind: HeadFieldKind
    required: bool = False
    choices: list[str] = []
    scope: Literal["class", "object"] = "class"
    """Whether the value is written to the pass class or to the pass object."""


class FamilyDescriptor(BaseModel):
    """Everything that is specific to one pass family."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    family_id: str
    label: str
    class_model: type
    object_model: type
    head_fields: list[HeadField]
    required_on_create: frozenset[str]
    """Fields Google demands on creation, beyond what Pydantic enforces."""


_REGISTRY: dict[str, FamilyDescriptor] = {}


def register(descriptor: FamilyDescriptor) -> FamilyDescriptor:
    """Add a descriptor to the registry and return it."""
    _REGISTRY[descriptor.family_id] = descriptor
    return descriptor


def get(family_id: str) -> FamilyDescriptor:
    """Return the descriptor for `family_id`, or raise KeyError."""
    try:
        return _REGISTRY[family_id]
    except KeyError:
        raise KeyError(f"unknown pass family: {family_id}") from None


def all_families() -> list[FamilyDescriptor]:
    """Return every registered descriptor, ordered by identifier."""
    return [_REGISTRY[key] for key in sorted(_REGISTRY)]


from . import loyalty as _loyalty  # noqa: E402,F401  (populates the registry)
