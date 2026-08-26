"""The draft model enforces what Google's structures imply."""

import pytest
from pydantic import ValidationError

from edutap.pass_designer.draft.models import Cell, FieldRef, Line, Row


def _text(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="text", module_id=module_id)])


def test_a_cell_may_carry_a_single_value() -> None:
    cell = Cell(first=_text("name"))

    assert cell.first is not None
    assert cell.second is None


def test_second_value_requires_a_first_value() -> None:
    with pytest.raises(ValidationError, match="second"):
        Cell(second=_text("name"))


def test_a_fallback_chain_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        Line(fallback_chain=[])


def test_a_row_holds_between_one_and_three_cells() -> None:
    assert len(Row(cells=[Cell(first=_text("a"))]).cells) == 1

    with pytest.raises(ValidationError):
        Row(cells=[])

    with pytest.raises(ValidationError):
        Row(cells=[Cell(first=_text(str(index))) for index in range(4)])
