"""The field catalogue: what a data provider can deliver.

The shape is `CatalogueField` as `edutap.pass_builder` already defines it. The
file shipped here is a neutral example; a real catalogue is loaded into the
running tool and is never committed to this public repository.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel


class CatalogueField(BaseModel):
    """One field a data provider can deliver."""

    key: str
    value_type: str
    label: str | None = None
    required: bool = False
    description: str | None = None


class CatalogueError(Exception):
    """A catalogue document at `path` is malformed.

    Deliberately not a `KeyError`: `/validate` and `/export` already catch
    `KeyError` to turn an unknown pass family into a `400`, and a malformed
    catalogue is a different failure entirely — a server misconfiguration,
    not bad user input. A distinct type keeps the two from colliding in the
    router's exception handling.
    """

    def __init__(self, path: Path, problem: str) -> None:
        """Build the error and its message from `path` and `problem`."""
        super().__init__(f"catalogue at {path} is malformed: {problem}")
        self.path = path
        self.problem = problem


def load_catalogue(path: Path) -> list[CatalogueField]:
    """Read a catalogue document and return its fields."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if "fields" not in document:
        raise CatalogueError(path, "missing the top-level 'fields' key")
    return [CatalogueField(**entry) for entry in document["fields"]]


def catalogue_types(fields: Iterable[CatalogueField]) -> dict[str, str]:
    """Return the `key -> value_type` mapping the other modules expect."""
    return {field.key: field.value_type for field in fields}
