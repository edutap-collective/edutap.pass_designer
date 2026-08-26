"""`load_catalogue` fails loudly, and names the file, on a malformed document."""

import json
from pathlib import Path

import pytest

from edutap.pass_designer.personas.catalogue import CatalogueError, load_catalogue


def test_a_document_without_a_fields_key_raises_a_named_catalogue_error(
    tmp_path: Path,
) -> None:
    catalogue_path = tmp_path / "catalogue.json"
    catalogue_path.write_text(json.dumps({"not_fields": []}), encoding="utf-8")

    with pytest.raises(CatalogueError) as excinfo:
        load_catalogue(catalogue_path)

    assert excinfo.value.path == catalogue_path
    assert str(catalogue_path) in str(excinfo.value)
    assert "fields" in str(excinfo.value)
