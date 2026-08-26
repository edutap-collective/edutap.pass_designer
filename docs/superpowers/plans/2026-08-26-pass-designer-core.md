# Pass Designer Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend of `edutap.pass_designer` — the draft model, the
family descriptors, import, export, validation and preview personas — up to a
running FastAPI service that round-trips a complete Loyalty pass template.

**Architecture:** A flat intermediate model (`Draft`) sits between the editor
and Google's deeply nested `ClassTemplateInfo`. Everything family-specific
lives in a descriptor written as Python code; everything else — grid, import,
export, validation, personas — is family-independent and written once. The
Pydantic models of `edutap.wallet-google` are the last word on what a valid
export looks like; this package never hand-builds a wallet dict.

**Tech Stack:** Python 3.12+, uv, FastAPI, Pydantic v2, `edutap.wallet-google`
3.0.0b2, Faker, pytest with anyio, ruff, ty.

**Spec:** [`docs/superpowers/specs/2026-08-26-pass-designer-design.md`](../specs/2026-08-26-pass-designer-design.md)

**Scope of this plan.** The spec covers a backend and a React editor. This plan
is the backend alone, because the editor consumes the descriptor endpoint and
the OpenAPI schema that this plan produces — the order is forced, not chosen.
It ends with working, testable software: a service that imports a Loyalty class
and object, validates them, resolves placeholders against a persona, and
exports the three artefacts. The React editor is a second plan; the remaining
six families are a third, and are pure descriptor work by then.

## Global Constraints

- Python `>=3.12`. Environments via `uv sync`; never `pip` or `python -m venv`
  directly.
- Dev tooling in `[dependency-groups]` (PEP 735), not in
  `[project.optional-dependencies]`.
- Repository language is **English** — code, comments, docs, commit messages.
- `edutap.wallet-google` is pinned to `3.0.0b2`; it is a beta and an unpinned
  floor would move under us.
- Async-first. No blocking calls in an async path.
- Placeholder syntax is `${dotted.field}`; `$$` is a literal dollar sign;
  substitution happens in string **values** only, never in dictionary keys.
- `textModulesData` at most 10 per level; `linksModuleData` at most 10 combined.
  Warn from the 6th entry, refuse the 11th.
- `TextModuleData.header` is capped at 35 characters and `body` at 500 by the
  upstream model — surface those limits, do not re-implement them.
- No real person's data anywhere, in tests or fixtures. Personas come from
  Faker with a fixed seed.
- The checked-in catalogue is a neutral example. Never commit an institution's
  field catalogue to this public repository.
- Every task ends with `make lint` and `make test-local` green before the
  commit step.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `Makefile`, `tox.ini`, `.pre-commit-config.yaml`,
  `.gitignore`
- Create: `src/edutap/pass_designer/__init__.py`
- Test: `tests/test_package.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installable `edutap.pass_designer` package and the commands
  `make lint`, `make reformat`, `make test-local` used by every later task.

- [ ] **Step 1: Write the failing test**

`tests/test_package.py`:

```python
"""The package is importable and declares its version."""


def test_package_exposes_a_version() -> None:
    import edutap.pass_designer

    assert isinstance(edutap.pass_designer.__version__, str)
    assert edutap.pass_designer.__version__
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_package.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edutap.pass_designer'`.

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[project]
name = "edutap.pass_designer"
version = "0.1.0.dev0"
description = "Visual designer for Google Wallet passes"
requires-python = ">=3.12"
readme = "README.md"
license = { text = "EUPL-1.2" }
dependencies = [
    "edutap.wallet-google==3.0.0b2",
    "fastapi>=0.115",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "faker>=40.0",
    "uvicorn[standard]>=0.32",
]

[dependency-groups]
dev = [
    "pdbp>=1.6",
    { include-group = "test" },
    { include-group = "typecheck" },
]
test = [
    "pytest>=8.3",
    "anyio>=4.6",
    "httpx>=0.27",
]
typecheck = ["ty>=0.0.1a1"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/edutap"]

[tool.ruff]
line-length = 88
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "B", "I", "UP", "D", "S"]
ignore = ["D203", "D213"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "D103"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

- [ ] **Step 4: Write the package module**

`src/edutap/pass_designer/__init__.py`:

```python
"""Visual designer for Google Wallet passes."""

__version__ = "0.1.0.dev0"
```

- [ ] **Step 5: Write the `Makefile`**

```make
.PHONY: lint reformat test-local test-integration docs

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run ty check src

reformat:
	uv run ruff format src tests
	uv run ruff check --fix src tests

test-local:
	uv run pytest tests -m "not integration"

test-integration:
	uv run pytest tests -m integration
```

- [ ] **Step 6: Write `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.0
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
```

- [ ] **Step 7: Run the test and the linters**

Run: `uv sync --group dev && make test-local && make lint`
Expected: the test passes; ruff and ty report no findings.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml Makefile tox.ini .pre-commit-config.yaml .gitignore \
        src/edutap/pass_designer/__init__.py tests/test_package.py
git commit -m "chore: scaffold the package, tooling and make targets"
```

---

### Task 2: The draft model

**Files:**
- Create: `src/edutap/pass_designer/draft/__init__.py`
- Create: `src/edutap/pass_designer/draft/models.py`
- Test: `tests/draft/test_models.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `FieldRef(kind, module_id, date_format)`, `Line(fallback_chain)`,
  `Cell(first, second)`, `Row(cells)`, `ListView(first_row, second_row)`,
  `TextModuleDraft(module_id, header, value, bound)`,
  `ImageModuleDraft(module_id, uri, bound)`,
  `LinkModuleDraft(uri, description)`,
  `RedemptionSettings(smart_tap_enabled, redemption_issuers, redemption_value, barcode_type, barcode_value)`,
  `Draft(...)`. Every later task builds on these names.

- [ ] **Step 1: Write the failing tests**

`tests/draft/test_models.py`:

```python
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
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/draft/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edutap.pass_designer.draft'`.

- [ ] **Step 3: Write the model**

`src/edutap/pass_designer/draft/models.py`:

```python
"""The editor's intermediate model.

Google nests a card row six levels deep. Editing that directly is unpleasant
and error-prone, so the editor works on this flat model and translates only at
the edges — see `exporter` and `importer`.
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class FieldRef(BaseModel):
    """One reference in a fallback chain."""

    kind: Literal["text", "image"]
    module_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    date_format: str | None = None

    @property
    def field_path(self) -> str:
        """Return the `fieldPath` Google expects for this reference."""
        collection = "textModulesData" if self.kind == "text" else "imageModulesData"
        return f"object.{collection}['{self.module_id}']"


class Line(BaseModel):
    """A displayed value.

    `fallback_chain` is a list of things to *try*, not a list of things to
    show: Google displays the first reference that points at a non-empty
    field. This is how one template serves several kinds of person.
    """

    fallback_chain: Annotated[list[FieldRef], Field(min_length=1)]


class Cell(BaseModel):
    """One column of a front row, or one entry of the back list.

    When both values are set Google renders them as a single element with a
    slash between them, and it refuses a second value without a first.
    """

    first: Line | None = None
    second: Line | None = None

    @model_validator(mode="after")
    def _second_requires_first(self) -> Self:
        if self.second is not None and self.first is None:
            message = "second value requires a first value"
            raise ValueError(message)
        return self


class Row(BaseModel):
    """A front row: one, two or three cells."""

    cells: Annotated[list[Cell], Field(min_length=1, max_length=3)]


class TransitOption(BaseModel):
    """The Transit-only alternative to a field reference in the list view."""

    option: str


class ListView(BaseModel):
    """The two rows of the Wallet overview entry.

    `thirdRowOption` is deprecated upstream and is not modelled here.
    """

    first_row: Line | TransitOption | None = None
    second_row: Line | None = None


class BarcodeSection(BaseModel):
    """Text above and below the code area on the front of the card.

    Google offers three slots; two above the code and one below it.
    """

    first_top: Line | None = None
    second_top: Line | None = None
    first_bottom: Line | None = None


class TextModuleDraft(BaseModel):
    """One text module, either a constant or bound to a provider field."""

    module_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    header: str | None = Field(default=None, max_length=35)
    value: str = ""
    bound: bool = False


class ImageModuleDraft(BaseModel):
    """One image module. `uri` is exported; local previews never are."""

    module_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    uri: str = ""
    bound: bool = False


class LinkModuleDraft(BaseModel):
    """One entry of the link block on the back of the pass."""

    uri: str
    description: str | None = None


class RedemptionSettings(BaseModel):
    """How the pass is redeemed: over NFC, visually, or both."""

    smart_tap_enabled: bool = False
    redemption_issuers: list[str] = []
    redemption_value: str | None = None
    barcode_type: str | None = None
    barcode_value: str | None = None


class Draft(BaseModel):
    """A complete pass design, independent of Google's structures."""

    family: str
    head: dict[str, str] = {}
    front_rows: list[Row] = []
    barcode_section: BarcodeSection | None = None
    back_items: list[Cell] = []
    list_view: ListView = ListView()
    text_modules: list[TextModuleDraft] = []
    image_modules: list[ImageModuleDraft] = []
    link_modules: list[LinkModuleDraft] = []
    redemption: RedemptionSettings = RedemptionSettings()
    unmapped: dict[str, Any] = {}
```

`src/edutap/pass_designer/draft/__init__.py`:

```python
"""The editor's intermediate model."""
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/draft/test_models.py -v`
Expected: all four PASS.

- [ ] **Step 5: Run the linters and commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/draft tests/draft
git commit -m "feat: add the draft model with fallback chains and cell rules"
```

---

### Task 3: Placeholder utilities

**Files:**
- Create: `src/edutap/pass_designer/placeholders.py`
- Test: `tests/test_placeholders.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `PLACEHOLDER_PATTERN`, `is_placeholder(text) -> bool`,
  `placeholder_for(field_key) -> str`,
  `source_field(text) -> str | None`,
  `check_dollar_signs(text) -> list[str]`,
  `scan(obj) -> list[tuple[str, str]]` returning `(json_pointer, source_field)`.

This mirrors `edutap.pass_builder.engine.placeholders`. It is written here
rather than imported because the builder is a service this package does not
otherwise depend on; `edutap.wallet_google#102` asks for a shared home, and
when it lands this module becomes a re-export.

- [ ] **Step 1: Write the failing tests**

`tests/test_placeholders.py`:

```python
"""Placeholders follow the manager's syntax exactly."""

from edutap.pass_designer.placeholders import (
    check_dollar_signs,
    is_placeholder,
    placeholder_for,
    scan,
    source_field,
)


def test_a_placeholder_wraps_a_dotted_field_key() -> None:
    assert placeholder_for("person.display_name") == "${person.display_name}"


def test_a_placeholder_is_recognised_and_its_field_extracted() -> None:
    assert is_placeholder("${person.display_name}")
    assert source_field("${person.display_name}") == "person.display_name"


def test_constant_text_is_not_a_placeholder() -> None:
    assert not is_placeholder("Ludwig-Maximilians-Universitat Munchen")
    assert source_field("plain text") is None


def test_a_doubled_dollar_sign_is_literal_and_allowed() -> None:
    assert check_dollar_signs("costs 5$$") == []


def test_a_lone_dollar_sign_is_reported() -> None:
    problems = check_dollar_signs("costs 5$")

    assert len(problems) == 1
    assert "$" in problems[0]


def test_scan_reports_a_json_pointer_for_every_placeholder() -> None:
    document = {
        "textModulesData": [
            {"id": "name", "body": "${person.display_name}"},
            {"id": "issuer", "body": "A constant"},
        ]
    }

    assert scan(document) == [
        ("/textModulesData/0/body", "person.display_name"),
    ]


def test_scan_ignores_dictionary_keys() -> None:
    assert scan({"${not.a.field}": "value"}) == []
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_placeholders.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the module**

`src/edutap/pass_designer/placeholders.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_placeholders.py -v`
Expected: all seven PASS.

- [ ] **Step 5: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/placeholders.py tests/test_placeholders.py
git commit -m "feat: add placeholder syntax matching the pass builder"
```

---

### Task 4: Family descriptors and the Loyalty descriptor

**Files:**
- Create: `src/edutap/pass_designer/platforms/__init__.py`
- Create: `src/edutap/pass_designer/platforms/google/__init__.py`
- Create: `src/edutap/pass_designer/platforms/google/families/__init__.py`
- Create: `src/edutap/pass_designer/platforms/google/families/loyalty.py`
- Test: `tests/families/test_registry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `HeadField(key, label, kind, required)`,
  `FamilyDescriptor(family_id, label, class_model, object_model, head_fields, required_on_create)`,
  `register(descriptor)`, `get(family_id) -> FamilyDescriptor`,
  `all_families() -> list[FamilyDescriptor]`.

Requiredness cannot be read off the Pydantic models — measured,
`LoyaltyClass` requires only `id` there, while Google's reference also demands
`issuerName`, `programName` and `reviewStatus`. The descriptor carries that
knowledge until `edutap.wallet_google#101` provides it upstream.

- [ ] **Step 1: Write the failing tests**

`tests/families/test_registry.py`:

```python
"""Descriptors are the only place a family differs from any other."""

import pytest

from edutap.pass_designer.platforms.google import families


def test_loyalty_is_registered() -> None:
    descriptor = families.get("loyalty")

    assert descriptor.family_id == "loyalty"
    assert descriptor.class_model.__name__ == "LoyaltyClass"
    assert descriptor.object_model.__name__ == "LoyaltyObject"


def test_loyalty_declares_what_google_requires_beyond_pydantic() -> None:
    descriptor = families.get("loyalty")

    assert "issuerName" in descriptor.required_on_create
    assert "programName" in descriptor.required_on_create
    assert "reviewStatus" in descriptor.required_on_create


def test_pydantic_alone_would_not_catch_those() -> None:
    descriptor = families.get("loyalty")
    pydantic_required = {
        name
        for name, field in descriptor.class_model.model_fields.items()
        if field.is_required()
    }

    assert "issuerName" not in pydantic_required


def test_an_unknown_family_is_refused_by_name() -> None:
    with pytest.raises(KeyError, match="nonesuch"):
        families.get("nonesuch")
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/families/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the descriptor mechanism**

`src/edutap/pass_designer/platforms/google/families/__init__.py`:

```python
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
```

- [ ] **Step 4: Write the Loyalty descriptor**

`src/edutap/pass_designer/platforms/google/families/loyalty.py`:

```python
"""The Loyalty family — the library card case.

`required_on_create` is copied from Google's REST reference, not derived from
the model: the model requires only `id`, while the API also insists on
`issuerName`, `programName` and `reviewStatus`.
See https://developers.google.com/wallet/retail/loyalty-cards/rest/v1/loyaltyclass
"""

from edutap.wallet_google.models.passes.retail import LoyaltyClass, LoyaltyObject

from . import FamilyDescriptor, HeadField, register

DESCRIPTOR = register(
    FamilyDescriptor(
        family_id="loyalty",
        label="Loyalty card",
        class_model=LoyaltyClass,
        object_model=LoyaltyObject,
        head_fields=[
            HeadField(key="issuerName", label="Issuer name", kind="text", required=True),
            HeadField(
                key="programName", label="Program name", kind="text", required=True
            ),
            HeadField(key="programLogo", label="Program logo", kind="image_uri"),
            HeadField(key="wideProgramLogo", label="Wide logo", kind="image_uri"),
            HeadField(key="heroImage", label="Hero image", kind="image_uri"),
            HeadField(key="hexBackgroundColor", label="Background", kind="colour"),
            HeadField(key="accountNameLabel", label="Account name label", kind="text"),
            HeadField(key="accountIdLabel", label="Account ID label", kind="text"),
            HeadField(key="accountName", label="Account name", kind="text"),
            HeadField(key="accountId", label="Account ID", kind="text"),
        ],
        required_on_create=frozenset({"issuerName", "programName", "reviewStatus"}),
    )
)
```

`src/edutap/pass_designer/platforms/__init__.py` and
`src/edutap/pass_designer/platforms/google/__init__.py`:

```python
"""Platform-specific code. Google is the only platform today."""
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/families/test_registry.py -v`
Expected: all four PASS.

- [ ] **Step 6: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/platforms tests/families
git commit -m "feat: add family descriptors and the loyalty family"
```

---

### Task 5: Export the class JSON

**Files:**
- Create: `src/edutap/pass_designer/exporter/__init__.py`
- Create: `src/edutap/pass_designer/exporter/class_json.py`
- Test: `tests/exporter/test_class_json.py`

**Interfaces:**
- Consumes: `Draft`, `Cell`, `Row`, `Line`, `FieldRef`, `ListView` (Task 2);
  `families.get` (Task 4).
- Produces: `build_class(draft, class_id) -> dict[str, Any]` — a validated
  dump of the family's class model, `exclude_none=True`.

- [ ] **Step 1: Write the failing tests**

`tests/exporter/test_class_json.py`:

```python
"""The class JSON carries the layout of all three views."""

from edutap.pass_designer.draft.models import (
    Cell,
    Draft,
    FieldRef,
    Line,
    ListView,
    RedemptionSettings,
    Row,
)
from edutap.pass_designer.exporter.class_json import build_class

CLASS_ID = "3388000000022141777.library.demo"


def _text(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="text", module_id=module_id)])


def _image(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="image", module_id=module_id)])


def _draft(**overrides: object) -> Draft:
    base = {
        "family": "loyalty",
        "head": {"issuerName": "Example University", "programName": "Library"},
    }
    return Draft(**{**base, **overrides})


def test_a_two_cell_row_becomes_two_items() -> None:
    draft = _draft(front_rows=[Row(cells=[Cell(first=_text("name")), Cell(first=_image("photo"))])])

    rows = build_class(draft, CLASS_ID)["classTemplateInfo"]["cardTemplateOverride"][
        "cardRowTemplateInfos"
    ]

    assert "twoItems" in rows[0]
    start = rows[0]["twoItems"]["startItem"]["firstValue"]["fields"]
    end = rows[0]["twoItems"]["endItem"]["firstValue"]["fields"]
    assert start[0]["fieldPath"] == "object.textModulesData['name']"
    assert end[0]["fieldPath"] == "object.imageModulesData['photo']"


def test_a_fallback_chain_becomes_several_field_references() -> None:
    line = Line(
        fallback_chain=[
            FieldRef(kind="text", module_id="staff_id"),
            FieldRef(kind="text", module_id="student_id"),
        ]
    )
    draft = _draft(front_rows=[Row(cells=[Cell(first=line)])])

    rows = build_class(draft, CLASS_ID)["classTemplateInfo"]["cardTemplateOverride"][
        "cardRowTemplateInfos"
    ]
    fields = rows[0]["oneItem"]["item"]["firstValue"]["fields"]

    assert [field["fieldPath"] for field in fields] == [
        "object.textModulesData['staff_id']",
        "object.textModulesData['student_id']",
    ]


def test_the_back_is_a_flat_list_of_single_items() -> None:
    draft = _draft(back_items=[Cell(first=_text("a")), Cell(first=_text("b"))])

    details = build_class(draft, CLASS_ID)["classTemplateInfo"][
        "detailsTemplateOverride"
    ]["detailsItemInfos"]

    assert len(details) == 2
    assert "item" in details[0]
    assert "twoItems" not in details[0]


def test_the_list_view_carries_two_rows_and_no_third() -> None:
    draft = _draft(list_view=ListView(first_row=_text("a"), second_row=_text("b")))

    list_override = build_class(draft, CLASS_ID)["classTemplateInfo"][
        "listTemplateOverride"
    ]

    assert "firstRowOption" in list_override
    assert "secondRowOption" in list_override
    assert "thirdRowOption" not in list_override


def test_the_barcode_section_belongs_to_the_front() -> None:
    from edutap.pass_designer.draft.models import BarcodeSection

    draft = _draft(barcode_section=BarcodeSection(first_bottom=_text("hint")))

    section = build_class(draft, CLASS_ID)["classTemplateInfo"][
        "cardBarcodeSectionDetails"
    ]

    assert (
        section["firstBottomDetail"]["fieldSelector"]["fields"][0]["fieldPath"]
        == "object.textModulesData['hint']"
    )
    assert "firstTopDetail" not in section


def test_smart_tap_settings_land_on_the_class() -> None:
    draft = _draft(
        redemption=RedemptionSettings(
            smart_tap_enabled=True, redemption_issuers=["3388000000022141777"]
        )
    )

    result = build_class(draft, CLASS_ID)

    assert result["enableSmartTap"] is True
    assert result["redemptionIssuers"] == ["3388000000022141777"]


def test_head_fields_are_written_through() -> None:
    result = build_class(_draft(), CLASS_ID)

    assert result["issuerName"] == "Example University"
    assert result["programName"] == "Library"
    assert result["id"] == CLASS_ID
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/exporter/test_class_json.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the exporter**

`src/edutap/pass_designer/exporter/class_json.py`:

```python
"""Translate a `Draft` into the family's Google Wallet class."""

from typing import Any

from edutap.wallet_google.models.datatypes.class_template_info import (
    BarcodeSectionDetail,
    CardBarcodeSectionDetails,
    CardRowOneItem,
    CardRowTemplateInfo,
    CardRowThreeItems,
    CardRowTwoItems,
    CardTemplateOverride,
    ClassTemplateInfo,
    DetailsItemInfo,
    DetailsTemplateOverride,
    FieldReference,
    FieldSelector,
    FirstRowOption,
    ListTemplateOverride,
    TemplateItem,
)

from ..draft.models import BarcodeSection, Cell, Draft, Line, ListView, Row
from ..platforms.google import families


def _selector(line: Line) -> FieldSelector:
    """Turn a fallback chain into the selector Google reads top-down."""
    return FieldSelector(
        fields=[
            FieldReference(fieldPath=reference.field_path, dateFormat=reference.date_format)
            for reference in line.fallback_chain
        ]
    )


def _item(cell: Cell) -> TemplateItem:
    return TemplateItem(
        firstValue=_selector(cell.first) if cell.first else None,
        secondValue=_selector(cell.second) if cell.second else None,
    )


def _row(row: Row) -> CardRowTemplateInfo:
    items = [_item(cell) for cell in row.cells]
    if len(items) == 1:
        return CardRowTemplateInfo(oneItem=CardRowOneItem(item=items[0]))
    if len(items) == 2:
        return CardRowTemplateInfo(
            twoItems=CardRowTwoItems(startItem=items[0], endItem=items[1])
        )
    return CardRowTemplateInfo(
        threeItems=CardRowThreeItems(
            startItem=items[0], middleItem=items[1], endItem=items[2]
        )
    )


def _list_override(view: ListView) -> ListTemplateOverride | None:
    if view.first_row is None and view.second_row is None:
        return None
    first: FirstRowOption | None = None
    if isinstance(view.first_row, Line):
        first = FirstRowOption(fieldOption=_selector(view.first_row))
    return ListTemplateOverride(
        firstRowOption=first,
        secondRowOption=_selector(view.second_row) if view.second_row else None,
    )


def _barcode_section(section: BarcodeSection | None) -> CardBarcodeSectionDetails | None:
    """Turn the three optional slots around the code into their details."""
    if section is None:
        return None

    def detail(line: Line | None) -> BarcodeSectionDetail | None:
        return BarcodeSectionDetail(fieldSelector=_selector(line)) if line else None

    details = CardBarcodeSectionDetails(
        firstTopDetail=detail(section.first_top),
        secondTopDetail=detail(section.second_top),
        firstBottomDetail=detail(section.first_bottom),
    )
    if all(
        value is None
        for value in (
            details.firstTopDetail,
            details.secondTopDetail,
            details.firstBottomDetail,
        )
    ):
        return None
    return details


def _template_info(draft: Draft) -> ClassTemplateInfo | None:
    card = (
        CardTemplateOverride(cardRowTemplateInfos=[_row(row) for row in draft.front_rows])
        if draft.front_rows
        else None
    )
    details = (
        DetailsTemplateOverride(
            detailsItemInfos=[DetailsItemInfo(item=_item(cell)) for cell in draft.back_items]
        )
        if draft.back_items
        else None
    )
    lists = _list_override(draft.list_view)
    barcode_section = _barcode_section(draft.barcode_section)
    if card is None and details is None and lists is None and barcode_section is None:
        return None
    return ClassTemplateInfo(
        cardBarcodeSectionDetails=barcode_section,
        cardTemplateOverride=card,
        detailsTemplateOverride=details,
        listTemplateOverride=lists,
    )


def build_class(draft: Draft, class_id: str) -> dict[str, Any]:
    """Return the family's class as a plain dict, ready to be written out.

    The dict is produced by the upstream Pydantic model, so anything it
    contains has already passed that model's validation.
    """
    descriptor = families.get(draft.family)
    payload: dict[str, Any] = {"id": class_id, **draft.head}

    template_info = _template_info(draft)
    if template_info is not None:
        payload["classTemplateInfo"] = template_info

    if draft.redemption.smart_tap_enabled:
        payload["enableSmartTap"] = True
        payload["redemptionIssuers"] = draft.redemption.redemption_issuers

    wallet_class = descriptor.class_model(**payload)
    exported = wallet_class.model_dump(exclude_none=True, mode="json")
    return {**draft.unmapped.get("class", {}), **exported}
```

`src/edutap/pass_designer/exporter/__init__.py`:

```python
"""Turn a `Draft` into the artefacts the pass builder manager consumes."""
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/exporter/test_class_json.py -v`
Expected: all seven PASS. If `thirdRowOption` appears in the output, the upstream
`exclude=True` has changed — stop and check `edutap.wallet-google` rather than
filtering it here.

- [ ] **Step 5: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/exporter tests/exporter
git commit -m "feat: export the class json for all three views"
```

---

### Task 6: Export the object JSON and the mapping rules

**Files:**
- Create: `src/edutap/pass_designer/exporter/object_json.py`
- Create: `src/edutap/pass_designer/exporter/mappings.py`
- Test: `tests/exporter/test_object_json.py`
- Test: `tests/exporter/test_mappings.py`

**Interfaces:**
- Consumes: `Draft`, `TextModuleDraft`, `ImageModuleDraft`, `LinkModuleDraft`,
  `RedemptionSettings` (Task 2); `placeholder_for`, `scan` (Task 3);
  `families.get` (Task 4).
- Produces: `build_object(draft, object_id, class_id) -> dict[str, Any]`;
  `build_mappings(object_json, catalogue) -> dict[str, Any]` returning
  `{"rules": [...]}` in the shape of `MappingRulesRequest`.

- [ ] **Step 1: Write the failing tests for the object**

`tests/exporter/test_object_json.py`:

```python
"""The object carries constants as they are and bindings as placeholders."""

from edutap.pass_designer.draft.models import (
    Draft,
    ImageModuleDraft,
    RedemptionSettings,
    TextModuleDraft,
)
from edutap.pass_designer.exporter.object_json import build_object

CLASS_ID = "3388000000022141777.library.demo"
OBJECT_ID = "3388000000022141777.specimen.object"


def _draft(**overrides: object) -> Draft:
    return Draft(**{"family": "loyalty", **overrides})


def test_a_bound_module_becomes_a_placeholder() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(
                module_id="name",
                header="Name",
                value="person.display_name",
                bound=True,
            )
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["textModulesData"]

    assert modules[0]["body"] == "${person.display_name}"
    assert modules[0]["id"] == "name"


def test_a_constant_module_is_written_through() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(module_id="issuer", header="Issuer", value="Example University")
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["textModulesData"]

    assert modules[0]["body"] == "Example University"


def test_an_image_module_carries_its_uri() -> None:
    draft = _draft(
        image_modules=[
            ImageModuleDraft(module_id="photo", uri="https://example.org/photo.png")
        ]
    )

    modules = build_object(draft, OBJECT_ID, CLASS_ID)["imageModulesData"]

    assert modules[0]["mainImage"]["sourceUri"]["uri"] == "https://example.org/photo.png"


def test_an_nfc_only_pass_emits_no_barcode_key_at_all() -> None:
    draft = _draft(
        redemption=RedemptionSettings(
            smart_tap_enabled=True, redemption_value="LIBRARY-CARD"
        )
    )

    result = build_object(draft, OBJECT_ID, CLASS_ID)

    assert "barcode" not in result
    assert result["smartTapRedemptionValue"] == "LIBRARY-CARD"


def test_a_barcode_is_emitted_when_one_is_wanted() -> None:
    draft = _draft(
        redemption=RedemptionSettings(barcode_type="AZTEC", barcode_value="12345")
    )

    barcode = build_object(draft, OBJECT_ID, CLASS_ID)["barcode"]

    assert barcode["type"] == "AZTEC"
    assert barcode["value"] == "12345"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/exporter/test_object_json.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the object exporter**

`src/edutap/pass_designer/exporter/object_json.py`:

```python
"""Translate a `Draft` into the family's Google Wallet object."""

from typing import Any

from edutap.wallet_google.models.datatypes.barcode import Barcode
from edutap.wallet_google.models.datatypes.data import (
    ImageModuleData,
    LinksModuleData,
    TextModuleData,
)
from edutap.wallet_google.models.datatypes.general import Image, ImageUri, Uri

from ..draft.models import Draft
from ..placeholders import placeholder_for
from ..platforms.google import families


def _value(raw: str, bound: bool) -> str:
    """Return a placeholder for a bound value, the text itself otherwise."""
    return placeholder_for(raw) if bound else raw


def build_object(draft: Draft, object_id: str, class_id: str) -> dict[str, Any]:
    """Return the family's specimen object as a plain dict.

    Values marked `bound` are written as `${field}` and filled by the pass
    builder at issuing time; everything else is a constant of the template.
    """
    descriptor = families.get(draft.family)
    payload: dict[str, Any] = {"id": object_id, "classId": class_id}

    if draft.text_modules:
        payload["textModulesData"] = [
            TextModuleData(
                id=module.module_id,
                header=module.header,
                body=_value(module.value, module.bound),
            )
            for module in draft.text_modules
        ]

    if draft.image_modules:
        payload["imageModulesData"] = [
            ImageModuleData(
                id=module.module_id,
                mainImage=Image(
                    sourceUri=ImageUri(uri=_value(module.uri, module.bound))
                ),
            )
            for module in draft.image_modules
        ]

    if draft.link_modules:
        payload["linksModuleData"] = LinksModuleData(
            uris=[
                Uri(uri=link.uri, description=link.description)
                for link in draft.link_modules
            ]
        )

    redemption = draft.redemption
    if redemption.redemption_value is not None:
        payload["smartTapRedemptionValue"] = redemption.redemption_value

    # No barcode key at all when none is wanted. This is the case Google's own
    # pass builder cannot express, and it is the normal case for us.
    if redemption.barcode_type:
        payload["barcode"] = Barcode(
            type=redemption.barcode_type, value=redemption.barcode_value or ""
        )

    wallet_object = descriptor.object_model(**payload)
    exported = wallet_object.model_dump(exclude_none=True, mode="json")
    return {**draft.unmapped.get("object", {}), **exported}
```

- [ ] **Step 4: Run the object tests**

Run: `uv run pytest tests/exporter/test_object_json.py -v`
Expected: all five PASS.

- [ ] **Step 5: Write the failing tests for the mapping rules**

`tests/exporter/test_mappings.py`:

```python
"""Mapping rules are derived from the placeholders that were written."""

from edutap.pass_designer.exporter.mappings import build_mappings

CATALOGUE = {"person.display_name": "text", "person.photo": "image"}


def test_every_placeholder_produces_a_rule() -> None:
    object_json = {
        "textModulesData": [{"id": "name", "body": "${person.display_name}"}]
    }

    rules = build_mappings(object_json, CATALOGUE)["rules"]

    assert len(rules) == 1
    assert rules[0]["source_field"] == "person.display_name"
    assert rules[0]["target"] == "/textModulesData/0/body"
    assert rules[0]["target_kind"] == "json_pointer"
    assert rules[0]["value_type"] == "text"


def test_the_value_type_comes_from_the_catalogue() -> None:
    object_json = {
        "imageModulesData": [
            {"id": "photo", "mainImage": {"sourceUri": {"uri": "${person.photo}"}}}
        ]
    }

    rules = build_mappings(object_json, CATALOGUE)["rules"]

    assert rules[0]["value_type"] == "image"


def test_a_field_missing_from_the_catalogue_defaults_to_text_and_is_flagged() -> None:
    object_json = {"textModulesData": [{"id": "x", "body": "${person.unknown}"}]}

    result = build_mappings(object_json, CATALOGUE)

    assert result["rules"][0]["value_type"] == "text"
    assert "person.unknown" in result["unknown_fields"]


def test_constants_produce_no_rules() -> None:
    object_json = {"textModulesData": [{"id": "issuer", "body": "A constant"}]}

    assert build_mappings(object_json, CATALOGUE)["rules"] == []
```

- [ ] **Step 6: Run them and watch them fail**

Run: `uv run pytest tests/exporter/test_mappings.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 7: Write the mapping builder**

`src/edutap/pass_designer/exporter/mappings.py`:

```python
"""Derive the binding table from the placeholders in an exported object.

The shape is `MappingRulesRequest` from `edutap.pass_builder`, so the same
payload can be written to a file today and sent to
`PUT /versions/{id}/mappings` later. Nothing new is invented here.
"""

from collections.abc import Mapping
from typing import Any

from ..placeholders import scan


def build_mappings(
    object_json: Mapping[str, Any], catalogue: Mapping[str, str]
) -> dict[str, Any]:
    """Return `{"rules": [...], "unknown_fields": [...]}` for `object_json`.

    `catalogue` maps a data-provider field key to its value-type slug. A field
    the catalogue does not know still produces a rule — dropping it would hide
    the binding entirely — but it is reported so the caller can refuse to
    export.
    """
    rules: list[dict[str, Any]] = []
    unknown: list[str] = []
    for position, (pointer, field_key) in enumerate(scan(object_json)):
        value_type = catalogue.get(field_key)
        if value_type is None:
            unknown.append(field_key)
            value_type = "text"
        rules.append(
            {
                "target_kind": "json_pointer",
                "target": pointer,
                "source_field": field_key,
                "value_type": value_type,
                "required": True,
                "default_value": None,
                "position": position,
            }
        )
    return {"rules": rules, "unknown_fields": sorted(set(unknown))}
```

- [ ] **Step 8: Run every exporter test**

Run: `uv run pytest tests/exporter -v`
Expected: all sixteen PASS (seven for the class, five for the object, four for
the mappings).

- [ ] **Step 9: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/exporter tests/exporter
git commit -m "feat: export the object json and derive the mapping rules"
```

---

### Task 7: Import and round-trip

**Files:**
- Create: `src/edutap/pass_designer/importer/__init__.py`
- Create: `src/edutap/pass_designer/importer/reader.py`
- Test: `tests/importer/test_round_trip.py`

**Interfaces:**
- Consumes: everything from Tasks 2–6.
- Produces: `read(class_json, object_json, family) -> Draft`.

- [ ] **Step 1: Write the failing tests**

`tests/importer/test_round_trip.py`:

```python
"""Importing what was exported must give back the same design."""

from edutap.pass_designer.draft.models import (
    Cell,
    Draft,
    FieldRef,
    Line,
    ListView,
    RedemptionSettings,
    Row,
    TextModuleDraft,
)
from edutap.pass_designer.exporter.class_json import build_class
from edutap.pass_designer.exporter.object_json import build_object
from edutap.pass_designer.importer.reader import read

CLASS_ID = "3388000000022141777.library.demo"
OBJECT_ID = "3388000000022141777.specimen.object"


def _text(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="text", module_id=module_id)])


ORIGINAL = Draft(
    family="loyalty",
    head={"issuerName": "Example University", "programName": "Library"},
    front_rows=[Row(cells=[Cell(first=_text("name")), Cell(first=_text("card_no"))])],
    back_items=[Cell(first=_text("group"))],
    list_view=ListView(first_row=_text("name"), second_row=_text("card_no")),
    text_modules=[
        TextModuleDraft(module_id="name", header="Name", value="person.display_name", bound=True),
        TextModuleDraft(module_id="card_no", header="Card number", value="42"),
        TextModuleDraft(module_id="group", header="Group", value="Staff"),
    ],
    redemption=RedemptionSettings(smart_tap_enabled=True, redemption_value="X"),
)


def test_a_design_survives_export_and_import() -> None:
    class_json = build_class(ORIGINAL, CLASS_ID)
    object_json = build_object(ORIGINAL, OBJECT_ID, CLASS_ID)

    restored = read(class_json, object_json, family="loyalty")

    assert restored.front_rows == ORIGINAL.front_rows
    assert restored.back_items == ORIGINAL.back_items
    assert restored.list_view == ORIGINAL.list_view
    assert restored.text_modules == ORIGINAL.text_modules


def test_a_placeholder_comes_back_as_a_bound_value() -> None:
    object_json = build_object(ORIGINAL, OBJECT_ID, CLASS_ID)

    restored = read(build_class(ORIGINAL, CLASS_ID), object_json, family="loyalty")
    name = next(m for m in restored.text_modules if m.module_id == "name")

    assert name.bound is True
    assert name.value == "person.display_name"


def test_unrecognised_fields_are_kept_and_written_back() -> None:
    class_json = {**build_class(ORIGINAL, CLASS_ID), "securityAnimation": {"animationType": "FOIL_SHIMMER"}}

    restored = read(class_json, build_object(ORIGINAL, OBJECT_ID, CLASS_ID), family="loyalty")
    again = build_class(restored, CLASS_ID)

    assert again["securityAnimation"] == {"animationType": "FOIL_SHIMMER"}
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/importer/test_round_trip.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the importer**

`src/edutap/pass_designer/importer/reader.py`:

```python
"""Read an exported class and object back into a `Draft`.

Anything this module does not understand is kept in `Draft.unmapped` and
written back unchanged on the next export. A tool that silently drops fields
when opening and saving is used exactly once.
"""

import re
from typing import Any

from ..draft.models import (
    BarcodeSection,
    Cell,
    Draft,
    FieldRef,
    ImageModuleDraft,
    Line,
    LinkModuleDraft,
    ListView,
    RedemptionSettings,
    Row,
    TextModuleDraft,
)
from ..placeholders import is_placeholder, source_field
from ..platforms.google import families

_FIELD_PATH = re.compile(r"^object\.(textModulesData|imageModulesData)\['([^']+)'\]$")

_CLASS_KEYS_HANDLED = {
    "id",
    "classTemplateInfo",
    "enableSmartTap",
    "redemptionIssuers",
}
_OBJECT_KEYS_HANDLED = {
    "id",
    "classId",
    "textModulesData",
    "imageModulesData",
    "linksModuleData",
    "smartTapRedemptionValue",
    "barcode",
}


def _reference(field_path: str) -> FieldRef | None:
    match = _FIELD_PATH.match(field_path)
    if match is None:
        return None
    collection, module_id = match.groups()
    kind = "text" if collection == "textModulesData" else "image"
    return FieldRef(kind=kind, module_id=module_id)


def _line(selector: dict[str, Any] | None) -> Line | None:
    if not selector:
        return None
    references = [
        reference
        for reference in (
            _reference(field.get("fieldPath", "")) for field in selector.get("fields", [])
        )
        if reference is not None
    ]
    return Line(fallback_chain=references) if references else None


def _cell(item: dict[str, Any] | None) -> Cell:
    if not item:
        return Cell()
    return Cell(first=_line(item.get("firstValue")), second=_line(item.get("secondValue")))


def _row(entry: dict[str, Any]) -> Row | None:
    if "oneItem" in entry:
        return Row(cells=[_cell(entry["oneItem"].get("item"))])
    if "twoItems" in entry:
        two = entry["twoItems"]
        return Row(cells=[_cell(two.get("startItem")), _cell(two.get("endItem"))])
    if "threeItems" in entry:
        three = entry["threeItems"]
        return Row(
            cells=[
                _cell(three.get("startItem")),
                _cell(three.get("middleItem")),
                _cell(three.get("endItem")),
            ]
        )
    return None


def read(
    class_json: dict[str, Any], object_json: dict[str, Any], family: str
) -> Draft:
    """Return the `Draft` that would export to `class_json` and `object_json`."""
    descriptor = families.get(family)
    template = class_json.get("classTemplateInfo", {})

    card = template.get("cardTemplateOverride", {}).get("cardRowTemplateInfos", [])
    front_rows = [row for row in (_row(entry) for entry in card) if row is not None]

    details = template.get("detailsTemplateOverride", {}).get("detailsItemInfos", [])
    back_items = [_cell(entry.get("item")) for entry in details]

    list_override = template.get("listTemplateOverride", {})
    list_view = ListView(
        first_row=_line(list_override.get("firstRowOption", {}).get("fieldOption")),
        second_row=_line(list_override.get("secondRowOption")),
    )

    # classTemplateInfo counts as handled, so anything inside it that is not
    # restored here is lost rather than kept in `unmapped`.
    section_json = template.get("cardBarcodeSectionDetails") or {}
    barcode_section = None
    if section_json:
        barcode_section = BarcodeSection(
            first_top=_line(section_json.get("firstTopDetail", {}).get("fieldSelector")),
            second_top=_line(section_json.get("secondTopDetail", {}).get("fieldSelector")),
            first_bottom=_line(
                section_json.get("firstBottomDetail", {}).get("fieldSelector")
            ),
        )

    head = {
        field.key: class_json[field.key]
        for field in descriptor.head_fields
        if field.key in class_json and isinstance(class_json[field.key], str)
    }

    text_modules = [
        TextModuleDraft(
            module_id=module["id"],
            header=module.get("header"),
            value=source_field(module.get("body", "")) or module.get("body", ""),
            bound=is_placeholder(module.get("body", "")),
        )
        for module in object_json.get("textModulesData", [])
        if module.get("id")
    ]

    image_modules = []
    for module in object_json.get("imageModulesData", []):
        uri = module.get("mainImage", {}).get("sourceUri", {}).get("uri", "")
        if module.get("id"):
            image_modules.append(
                ImageModuleDraft(
                    module_id=module["id"],
                    uri=source_field(uri) or uri,
                    bound=is_placeholder(uri),
                )
            )

    link_modules = [
        LinkModuleDraft(uri=entry.get("uri", ""), description=entry.get("description"))
        for entry in object_json.get("linksModuleData", {}).get("uris", [])
    ]

    barcode = object_json.get("barcode") or {}
    redemption = RedemptionSettings(
        smart_tap_enabled=bool(class_json.get("enableSmartTap")),
        redemption_issuers=list(class_json.get("redemptionIssuers", [])),
        redemption_value=object_json.get("smartTapRedemptionValue"),
        barcode_type=barcode.get("type"),
        barcode_value=barcode.get("value"),
    )

    known_class_keys = _CLASS_KEYS_HANDLED | {field.key for field in descriptor.head_fields}
    unmapped = {
        "class": {k: v for k, v in class_json.items() if k not in known_class_keys},
        "object": {k: v for k, v in object_json.items() if k not in _OBJECT_KEYS_HANDLED},
    }

    return Draft(
        family=family,
        head=head,
        front_rows=front_rows,
        barcode_section=barcode_section,
        back_items=back_items,
        list_view=list_view,
        text_modules=text_modules,
        image_modules=image_modules,
        link_modules=link_modules,
        redemption=redemption,
        unmapped=unmapped,
    )
```

`src/edutap/pass_designer/importer/__init__.py`:

```python
"""Read exported artefacts back into a `Draft`."""
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/importer -v`
Expected: all three PASS. A failure in the round-trip test names the field that
does not survive — fix the importer, never the assertion.

- [ ] **Step 5: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/importer tests/importer
git commit -m "feat: import class and object back into a draft, keeping unknowns"
```

---

### Task 8: Validation

**Files:**
- Create: `src/edutap/pass_designer/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: `Draft` and its parts (Task 2); `families.get` (Task 4);
  `check_dollar_signs` (Task 3).
- Produces: `Finding(severity, message, location)`,
  `validate(draft, catalogue) -> list[Finding]`,
  `MODULE_LIMIT = 10`, `MODULE_WARNING_THRESHOLD = 6`.

- [ ] **Step 1: Write the failing tests**

`tests/test_validation.py`:

```python
"""Validation catches what Google would swallow in silence."""

from edutap.pass_designer.draft.models import (
    Cell,
    Draft,
    FieldRef,
    Line,
    Row,
    TextModuleDraft,
)
from edutap.pass_designer.validation import validate

CATALOGUE = {"person.display_name": "text"}


def _text(module_id: str) -> Line:
    return Line(fallback_chain=[FieldRef(kind="text", module_id=module_id)])


def _draft(**overrides: object) -> Draft:
    base = {
        "family": "loyalty",
        "head": {"issuerName": "Example University", "programName": "Library"},
    }
    return Draft(**{**base, **overrides})


def test_a_field_path_without_a_module_is_an_error() -> None:
    draft = _draft(front_rows=[Row(cells=[Cell(first=_text("ghost"))])])

    findings = validate(draft, CATALOGUE)

    assert any(f.severity == "error" and "ghost" in f.message for f in findings)


def test_a_resolvable_field_path_produces_nothing() -> None:
    draft = _draft(
        front_rows=[Row(cells=[Cell(first=_text("name"))])],
        text_modules=[TextModuleDraft(module_id="name", value="x")],
    )

    assert [f for f in validate(draft, CATALOGUE) if f.severity == "error"] == []


def test_a_missing_required_head_field_is_an_error() -> None:
    draft = Draft(family="loyalty", head={"issuerName": "Example University"})

    findings = validate(draft, CATALOGUE)

    assert any("programName" in f.message for f in findings)


def test_the_sixth_text_module_produces_a_warning() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(module_id=f"m{index}", value="x") for index in range(6)
        ]
    )

    assert any(f.severity == "warning" and "10" in f.message for f in validate(draft, CATALOGUE))


def test_the_eleventh_text_module_is_an_error() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(module_id=f"m{index}", value="x") for index in range(11)
        ]
    )

    assert any(f.severity == "error" and "10" in f.message for f in validate(draft, CATALOGUE))


def test_a_bound_field_unknown_to_the_catalogue_is_a_warning() -> None:
    draft = _draft(
        text_modules=[
            TextModuleDraft(module_id="x", value="person.nonesuch", bound=True)
        ]
    )

    assert any("person.nonesuch" in f.message for f in validate(draft, CATALOGUE))


def test_a_lone_dollar_sign_in_a_constant_is_an_error() -> None:
    draft = _draft(text_modules=[TextModuleDraft(module_id="fee", value="costs 5$")])

    assert any(f.severity == "error" and "$" in f.message for f in validate(draft, CATALOGUE))
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the validator**

`src/edutap/pass_designer/validation.py`:

```python
"""Checks the Pydantic models cannot make.

The most important one is the first. Google discards a `fieldPath` that
refers to a module the object does not carry — silently. The row simply does
not appear, with no error at any layer, which makes it the one defect that
cannot be found by looking at either side alone.
"""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel

from .draft.models import Cell, Draft, Line
from .placeholders import check_dollar_signs
from .platforms.google import families

MODULE_LIMIT = 10
MODULE_WARNING_THRESHOLD = 6

Severity = Literal["error", "warning"]


class Finding(BaseModel):
    """One problem with a draft."""

    severity: Severity
    message: str
    location: str


def _lines(draft: Draft) -> list[tuple[str, Line]]:
    found: list[tuple[str, Line]] = []

    def collect(where: str, cell: Cell) -> None:
        for line in (cell.first, cell.second):
            if line is not None:
                found.append((where, line))

    for row_index, row in enumerate(draft.front_rows):
        for cell_index, cell in enumerate(row.cells):
            collect(f"front/row {row_index + 1}/cell {cell_index + 1}", cell)
    for item_index, cell in enumerate(draft.back_items):
        collect(f"back/item {item_index + 1}", cell)
    for name, line in (
        ("list/first row", draft.list_view.first_row),
        ("list/second row", draft.list_view.second_row),
    ):
        if isinstance(line, Line):
            found.append((name, line))
    return found


def _check_field_paths(draft: Draft) -> list[Finding]:
    text_ids = {module.module_id for module in draft.text_modules}
    image_ids = {module.module_id for module in draft.image_modules}
    findings: list[Finding] = []
    for where, line in _lines(draft):
        for reference in line.fallback_chain:
            known = text_ids if reference.kind == "text" else image_ids
            if reference.module_id not in known:
                findings.append(
                    Finding(
                        severity="error",
                        location=where,
                        message=(
                            f"no {reference.kind} module '{reference.module_id}' "
                            f"exists; Google discards this reference without "
                            f"reporting it and the value never appears"
                        ),
                    )
                )
    return findings


def _check_required_head_fields(draft: Draft) -> list[Finding]:
    descriptor = families.get(draft.family)
    findings: list[Finding] = []
    for key in sorted(descriptor.required_on_create):
        if key == "reviewStatus":
            continue  # carries a default in the upstream model
        if not draft.head.get(key):
            findings.append(
                Finding(
                    severity="error",
                    location="head",
                    message=f"Google requires '{key}' when the class is created",
                )
            )
    return findings


def _check_volume(draft: Draft) -> list[Finding]:
    findings: list[Finding] = []
    for label, count in (
        ("text modules", len(draft.text_modules)),
        ("links", len(draft.link_modules)),
    ):
        if count > MODULE_LIMIT:
            findings.append(
                Finding(
                    severity="error",
                    location=label,
                    message=(
                        f"{count} {label}; Google accepts at most {MODULE_LIMIT} "
                        f"and drops the rest without reporting it"
                    ),
                )
            )
        elif count >= MODULE_WARNING_THRESHOLD:
            findings.append(
                Finding(
                    severity="warning",
                    location=label,
                    message=f"{count} {label}; the limit is {MODULE_LIMIT}",
                )
            )
    return findings


def _check_values(draft: Draft, catalogue: Mapping[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for module in draft.text_modules:
        where = f"module '{module.module_id}'"
        if module.bound:
            if module.value not in catalogue:
                findings.append(
                    Finding(
                        severity="warning",
                        location=where,
                        message=(
                            f"'{module.value}' is not in the field catalogue; "
                            f"the pass builder will not be able to fill it"
                        ),
                    )
                )
            continue
        for problem in check_dollar_signs(module.value):
            findings.append(Finding(severity="error", location=where, message=problem))
    return findings


def validate(draft: Draft, catalogue: Mapping[str, str]) -> list[Finding]:
    """Return every problem found, errors and warnings together."""
    return [
        *_check_field_paths(draft),
        *_check_required_head_fields(draft),
        *_check_volume(draft),
        *_check_values(draft, catalogue),
    ]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_validation.py -v`
Expected: all seven PASS.

- [ ] **Step 5: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/validation.py tests/test_validation.py
git commit -m "feat: validate field paths, required head fields and volume limits"
```

---

### Task 9: Field catalogue and preview personas

**Files:**
- Create: `src/edutap/pass_designer/personas/__init__.py`
- Create: `src/edutap/pass_designer/personas/catalogue.py`
- Create: `src/edutap/pass_designer/personas/faker_map.py`
- Create: `src/edutap/pass_designer/personas/generator.py`
- Create: `data/catalogue.example.json`
- Test: `tests/personas/test_personas.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `CatalogueField(key, value_type, label, required, description)`,
  `load_catalogue(path) -> list[CatalogueField]`,
  `catalogue_types(fields) -> dict[str, str]`,
  `Persona(persona_id, label, locale, gender, values)`,
  `build_personas(fields) -> list[Persona]`.

- [ ] **Step 1: Write the example catalogue**

`data/catalogue.example.json` — neutral keys only; never an institution's:

```json
{
  "fields": [
    {"key": "person.display_name", "value_type": "text", "label": "Display name", "required": true, "description": "The name shown on the pass"},
    {"key": "person.given_name", "value_type": "text", "label": "Given name", "required": false, "description": null},
    {"key": "person.family_name", "value_type": "text", "label": "Family name", "required": false, "description": null},
    {"key": "person.date_of_birth", "value_type": "date", "label": "Date of birth", "required": false, "description": null},
    {"key": "person.photo", "value_type": "image", "label": "Photograph", "required": false, "description": "URL of the active photo version"},
    {"key": "affiliation.primary", "value_type": "text", "label": "Primary affiliation", "required": false, "description": null},
    {"key": "affiliation.unit", "value_type": "text", "label": "Organisational unit", "required": false, "description": null},
    {"key": "card.number", "value_type": "text", "label": "Card number", "required": true, "description": null},
    {"key": "card.valid_until", "value_type": "date", "label": "Valid until", "required": false, "description": null},
    {"key": "card.homepage", "value_type": "uri", "label": "Homepage", "required": false, "description": null}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

`tests/personas/test_personas.py`:

```python
"""Personas are coherent, reproducible and never real."""

from pathlib import Path

from edutap.pass_designer.personas.catalogue import catalogue_types, load_catalogue
from edutap.pass_designer.personas.generator import build_personas

CATALOGUE_PATH = Path("data/catalogue.example.json")


def test_the_example_catalogue_loads() -> None:
    fields = load_catalogue(CATALOGUE_PATH)

    assert any(field.key == "person.display_name" for field in fields)
    assert catalogue_types(fields)["person.date_of_birth"] == "date"


def test_the_three_genders_are_represented() -> None:
    personas = build_personas(load_catalogue(CATALOGUE_PATH))

    assert {persona.gender for persona in personas} >= {"female", "male", "non-binary"}


def test_generation_is_reproducible() -> None:
    fields = load_catalogue(CATALOGUE_PATH)

    first = build_personas(fields)
    second = build_personas(fields)

    assert [p.values for p in first] == [p.values for p in second]


def test_a_persona_is_internally_coherent() -> None:
    persona = build_personas(load_catalogue(CATALOGUE_PATH))[0]

    assert persona.values["person.display_name"].startswith(
        persona.values["person.given_name"]
    )
    assert persona.values["person.family_name"] in persona.values["person.display_name"]


def test_one_persona_has_deliberately_empty_fields() -> None:
    personas = build_personas(load_catalogue(CATALOGUE_PATH))

    sparse = [p for p in personas if any(value == "" for value in p.values.values())]
    assert sparse, "a sparse persona is the only way to see a fallback chain work"


def test_an_unmapped_field_is_visibly_generic() -> None:
    from edutap.pass_designer.personas.catalogue import CatalogueField

    fields = [CatalogueField(key="odd.thing", value_type="text", label="Odd")]
    persona = build_personas(fields)[0]

    assert persona.values["odd.thing"].startswith("text-")
```

- [ ] **Step 3: Run them and watch them fail**

Run: `uv run pytest tests/personas -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write the catalogue reader**

`src/edutap/pass_designer/personas/catalogue.py`:

```python
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


def load_catalogue(path: Path) -> list[CatalogueField]:
    """Read a catalogue document and return its fields."""
    document = json.loads(path.read_text(encoding="utf-8"))
    return [CatalogueField(**entry) for entry in document["fields"]]


def catalogue_types(fields: Iterable[CatalogueField]) -> dict[str, str]:
    """Return the `key -> value_type` mapping the other modules expect."""
    return {field.key: field.value_type for field in fields}
```

- [ ] **Step 5: Write the Faker mapping table**

`src/edutap/pass_designer/personas/faker_map.py`:

```python
"""Which Faker provider stands behind which catalogue field.

`value_type` alone is not enough — `text` covers a name, a faculty and a job
title equally well. The table is explicit and lives beside the catalogue so a
gap in it shows up in a diff. An unmapped field falls back to something
visibly generic rather than something plausible, so the gap is noticed rather
than believed.
"""

PROVIDER_BY_FIELD: dict[str, str] = {
    "person.given_name": "given_name",
    "person.family_name": "family_name",
    "person.display_name": "display_name",
    "person.date_of_birth": "date_of_birth",
    "person.photo": "photo_uri",
    "affiliation.primary": "affiliation",
    "affiliation.unit": "organisational_unit",
    "card.number": "card_number",
    "card.valid_until": "valid_until",
    "card.homepage": "homepage",
}
```

- [ ] **Step 6: Write the persona generator**

`src/edutap/pass_designer/personas/generator.py`:

```python
"""Build coherent, reproducible preview personas.

A persona draws its locale and gender once and derives everything else from
them, so the person has a name, a birth date and an affiliation that belong
together. Drawing each field independently would produce a name from one
country and a birthplace from another, and the preview would be useless for
judging a layout.

The seed is fixed so that comparing two layouts is not confounded by a
changing name.
"""

from collections.abc import Iterable, Sequence

from faker import Faker
from pydantic import BaseModel

from .catalogue import CatalogueField
from .faker_map import PROVIDER_BY_FIELD

SEED = 20260826

#: (identifier, label, locale, gender, sparse)
PERSONA_RECIPES: Sequence[tuple[str, str, str, str, bool]] = (
    ("de-female", "German, female", "de_DE", "female", False),
    ("en-male", "English, male", "en_US", "male", False),
    ("fr-nonbinary", "French, non-binary", "fr_FR", "non-binary", False),
    ("tr-female", "Turkish, female", "tr_TR", "female", False),
    ("zh-male", "Chinese, male", "zh_CN", "male", False),
    ("sparse", "Sparse — many fields empty", "de_DE", "non-binary", True),
)

#: Fields a sparse persona deliberately leaves empty, so that a fallback
#: chain has something to fall back from.
_SPARSE_EMPTY = {"person.date_of_birth", "affiliation.unit", "card.valid_until"}


class Persona(BaseModel):
    """One preview person: coherent, fictional, reproducible."""

    persona_id: str
    label: str
    locale: str
    gender: str
    values: dict[str, str]


def _name(faker: Faker, gender: str) -> tuple[str, str]:
    """Return `(given, family)` for the persona's gender."""
    if gender == "female":
        full = faker.name_female()
    elif gender == "male":
        full = faker.name_male()
    else:
        full = faker.name_nonbinary()
    parts = full.split()
    if len(parts) == 1:
        return parts[0], parts[0]
    return " ".join(parts[:-1]), parts[-1]


def _value(faker: Faker, provider: str | None, field: CatalogueField, given: str, family: str) -> str:
    if provider == "given_name":
        return given
    if provider == "family_name":
        return family
    if provider == "display_name":
        return f"{given} {family}"
    if provider == "date_of_birth":
        return faker.date_of_birth(minimum_age=18, maximum_age=70).strftime("%d.%m.%Y")
    if provider == "photo_uri":
        return "https://example.org/photo/specimen.png"
    if provider == "affiliation":
        return faker.random_element(["student", "staff", "member"])
    if provider == "organisational_unit":
        return faker.random_element(["Central Library", "IT Services", "Faculty Office"])
    if provider == "card_number":
        return faker.numerify("############")
    if provider == "valid_until":
        return faker.date_between(start_date="+180d", end_date="+900d").strftime("%d.%m.%Y")
    if provider == "homepage":
        return "https://example.org/"
    # Deliberately not plausible: a gap in the table must look like a gap.
    return f"{field.value_type}-{faker.numerify('####')}"


def build_personas(fields: Iterable[CatalogueField]) -> list[Persona]:
    """Return one persona per recipe, each filling every catalogue field."""
    catalogue = list(fields)
    personas: list[Persona] = []
    for offset, (persona_id, label, locale, gender, sparse) in enumerate(PERSONA_RECIPES):
        faker = Faker(locale)
        faker.seed_instance(SEED + offset)
        given, family = _name(faker, gender)
        values: dict[str, str] = {}
        for field in catalogue:
            if sparse and field.key in _SPARSE_EMPTY:
                values[field.key] = ""
                continue
            values[field.key] = _value(
                faker, PROVIDER_BY_FIELD.get(field.key), field, given, family
            )
        personas.append(
            Persona(
                persona_id=persona_id,
                label=label,
                locale=locale,
                gender=gender,
                values=values,
            )
        )
    return personas
```

`src/edutap/pass_designer/personas/__init__.py`:

```python
"""Preview personas and the field catalogue they fill."""
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/personas -v`
Expected: all six PASS. If `name_nonbinary` is missing for a locale, replace
that locale in `PERSONA_RECIPES` rather than silently falling back to a
gendered provider — a persona that lies about its own gender is worse than one
locale fewer.

- [ ] **Step 8: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/personas data/catalogue.example.json tests/personas
git commit -m "feat: add the field catalogue and coherent seeded personas"
```

---

### Task 10: The HTTP service, container and documentation

**Files:**
- Create: `src/edutap/pass_designer/settings.py`
- Create: `src/edutap/pass_designer/web/__init__.py`
- Create: `src/edutap/pass_designer/web/app.py`
- Create: `src/edutap/pass_designer/web/routers/design.py`
- Create: `Dockerfile`, `compose.yml`
- Create: `docs/how-to/run-the-service.md`
- Test: `tests/web/test_api.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `create_app() -> FastAPI` and the routes
  `GET /designer/v1/families`, `GET /designer/v1/personas`,
  `POST /designer/v1/validate`, `POST /designer/v1/export`,
  `POST /designer/v1/import`.

- [ ] **Step 1: Write the failing tests**

`tests/web/test_api.py`:

```python
"""The HTTP surface the editor will consume."""

import pytest
from httpx import ASGITransport, AsyncClient

from edutap.pass_designer.web.app import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance


DRAFT = {
    "family": "loyalty",
    "head": {"issuerName": "Example University", "programName": "Library"},
    "front_rows": [
        {"cells": [{"first": {"fallback_chain": [{"kind": "text", "module_id": "name"}]}}]}
    ],
    "text_modules": [
        {"module_id": "name", "header": "Name", "value": "person.display_name", "bound": True}
    ],
}


async def test_families_are_listed_with_their_head_fields(client: AsyncClient) -> None:
    response = await client.get("/designer/v1/families")

    assert response.status_code == 200
    loyalty = next(f for f in response.json() if f["family_id"] == "loyalty")
    assert any(field["key"] == "programName" for field in loyalty["head_fields"])


async def test_personas_are_offered_for_the_preview(client: AsyncClient) -> None:
    response = await client.get("/designer/v1/personas")

    assert response.status_code == 200
    assert {p["gender"] for p in response.json()} >= {"female", "male", "non-binary"}


async def test_validation_reports_an_unresolvable_field_path(client: AsyncClient) -> None:
    broken = {**DRAFT, "text_modules": []}

    response = await client.post("/designer/v1/validate", json={"draft": broken})

    assert response.status_code == 200
    assert any(f["severity"] == "error" for f in response.json()["findings"])


async def test_export_returns_all_three_artefacts(client: AsyncClient) -> None:
    response = await client.post(
        "/designer/v1/export",
        json={"draft": DRAFT, "class_id": "1.a", "object_id": "1.b"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["class_json"]["id"] == "1.a"
    assert body["object_json"]["textModulesData"][0]["body"] == "${person.display_name}"
    assert body["mappings"]["rules"][0]["source_field"] == "person.display_name"


async def test_export_refuses_a_draft_with_errors(client: AsyncClient) -> None:
    broken = {**DRAFT, "text_modules": []}

    response = await client.post(
        "/designer/v1/export",
        json={"draft": broken, "class_id": "1.a", "object_id": "1.b"},
    )

    assert response.status_code == 422


async def test_import_returns_a_draft(client: AsyncClient) -> None:
    exported = (
        await client.post(
            "/designer/v1/export",
            json={"draft": DRAFT, "class_id": "1.a", "object_id": "1.b"},
        )
    ).json()

    response = await client.post(
        "/designer/v1/import",
        json={
            "family": "loyalty",
            "class_json": exported["class_json"],
            "object_json": exported["object_json"],
        },
    )

    assert response.status_code == 200
    assert response.json()["text_modules"][0]["bound"] is True
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/web -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the settings**

`src/edutap/pass_designer/settings.py`:

```python
"""Configuration. Everything through pydantic-settings, no stray getenv."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the designer."""

    model_config = SettingsConfigDict(env_prefix="PASS_DESIGNER_")

    catalogue_path: Path = Path("data/catalogue.example.json")
    root_path: str = ""
    """Path prefix when served behind Traefik, e.g. `/portale/pass-designer`."""


def get_settings() -> Settings:
    """Return the settings, read from the environment."""
    return Settings()
```

- [ ] **Step 4: Write the router**

`src/edutap/pass_designer/web/routers/design.py`:

```python
"""The routes the editor consumes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...draft.models import Draft
from ...exporter.class_json import build_class
from ...exporter.mappings import build_mappings
from ...exporter.object_json import build_object
from ...importer.reader import read
from ...personas.catalogue import catalogue_types, load_catalogue
from ...personas.generator import Persona, build_personas
from ...platforms.google import families
from ...settings import Settings, get_settings
from ...validation import Finding, validate

router = APIRouter(prefix="/designer/v1", tags=["designer"])


class ValidateRequest(BaseModel):
    draft: Draft


class ValidateResponse(BaseModel):
    findings: list[Finding]


class ExportRequest(BaseModel):
    draft: Draft
    class_id: str
    object_id: str


class ExportResponse(BaseModel):
    class_json: dict[str, Any]
    object_json: dict[str, Any]
    mappings: dict[str, Any]


class ImportRequest(BaseModel):
    family: str
    class_json: dict[str, Any]
    object_json: dict[str, Any]


def _catalogue(settings: Settings) -> dict[str, str]:
    return catalogue_types(load_catalogue(settings.catalogue_path))


@router.get("/families")
async def list_families() -> list[dict[str, Any]]:
    """Return every pass family, with the head fields its form needs."""
    return [
        {
            "family_id": descriptor.family_id,
            "label": descriptor.label,
            "head_fields": [field.model_dump() for field in descriptor.head_fields],
            "required_on_create": sorted(descriptor.required_on_create),
        }
        for descriptor in families.all_families()
    ]


@router.get("/personas")
async def list_personas(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> list[Persona]:
    """Return the preview personas, generated from the loaded catalogue."""
    return build_personas(load_catalogue(settings.catalogue_path))


@router.post("/validate")
async def validate_draft(
    request: ValidateRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ValidateResponse:
    """Return every problem with a draft, without exporting anything."""
    return ValidateResponse(findings=validate(request.draft, _catalogue(settings)))


@router.post("/export")
async def export_draft(
    request: ExportRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ExportResponse:
    """Return the three artefacts, refusing a draft that carries errors."""
    catalogue = _catalogue(settings)
    findings = validate(request.draft, catalogue)
    errors = [finding for finding in findings if finding.severity == "error"]
    if errors:
        raise HTTPException(
            status_code=422,
            detail=[finding.model_dump() for finding in errors],
        )

    class_json = build_class(request.draft, request.class_id)
    object_json = build_object(request.draft, request.object_id, request.class_id)
    return ExportResponse(
        class_json=class_json,
        object_json=object_json,
        mappings=build_mappings(object_json, catalogue),
    )


@router.post("/import")
async def import_artefacts(request: ImportRequest) -> Draft:
    """Return the draft that would export to the given class and object."""
    try:
        return read(request.class_json, request.object_json, family=request.family)
    except KeyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
```

- [ ] **Step 5: Write the application factory**

`src/edutap/pass_designer/web/app.py`:

```python
"""The FastAPI application."""

from fastapi import FastAPI

from ..settings import get_settings
from .routers import design


def create_app() -> FastAPI:
    """Return a configured application instance."""
    settings = get_settings()
    app = FastAPI(
        title="eduTAP Pass Designer",
        version="0.1.0",
        root_path=settings.root_path,
    )
    app.include_router(design.router)
    return app


app = create_app()
```

`src/edutap/pass_designer/web/__init__.py` and
`src/edutap/pass_designer/web/routers/__init__.py`:

```python
"""HTTP surface."""
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/web -v`
Expected: all six PASS.

- [ ] **Step 7: Write the container files**

`Dockerfile` — multi-stage, slim base, `pip install` inside the image:

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
COPY data ./data
EXPOSE 8000
CMD ["uvicorn", "edutap.pass_designer.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

`compose.yml`:

```yaml
services:
  designer:
    build: .
    ports:
      - "8000:8000"
    environment:
      PASS_DESIGNER_CATALOGUE_PATH: /app/data/catalogue.example.json
```

- [ ] **Step 8: Verify the container serves the API**

Run:

```bash
docker compose up -d --build
curl -sf http://localhost:8000/designer/v1/families | head -c 200
docker compose down
```

Expected: the families array comes back. On an Apple Silicon machine add
`--platform linux/amd64` to the build if the image is destined for the cluster;
the nodes are x86_64 and an arm64 image fails at start with
`exec format error`.

- [ ] **Step 9: Write the how-to**

`docs/how-to/run-the-service.md`:

````markdown
# Run the designer service

## In a container

```console
docker compose up -d --build
```

The API is then on <http://localhost:8000>, and its OpenAPI documentation on
<http://localhost:8000/docs>.

```console
docker compose down
```

On an Apple Silicon machine, add `--platform linux/amd64` to the build when the
image is meant for the cluster. The nodes are x86_64, and an arm64 image starts
and immediately dies with `exec format error`.

## Without a container

```console
uv sync --group dev
uv run uvicorn edutap.pass_designer.web.app:app --reload
```

## The five routes

```console
curl -s localhost:8000/designer/v1/families
curl -s localhost:8000/designer/v1/personas

curl -s localhost:8000/designer/v1/validate \
  -H 'content-type: application/json' \
  -d '{"draft": {"family": "loyalty", "head": {}}}'

curl -s localhost:8000/designer/v1/export \
  -H 'content-type: application/json' \
  -d '{"draft": {"family": "loyalty",
                 "head": {"issuerName": "Example University",
                          "programName": "Library"}},
       "class_id": "ISSUER.library", "object_id": "ISSUER.specimen"}'

curl -s localhost:8000/designer/v1/import \
  -H 'content-type: application/json' \
  -d '{"family": "loyalty", "class_json": {}, "object_json": {}}'
```

`/export` answers `422` with a list of findings when the draft carries errors.
Call `/validate` first if you want warnings as well.

## Using a real field catalogue

The catalogue shipped in `data/catalogue.example.json` is a neutral example.
Point the service at a real one instead:

```console
docker compose run --rm \
  -e PASS_DESIGNER_CATALOGUE_PATH=/app/data/catalogue.json \
  -v "$PWD/catalogue.json:/app/data/catalogue.json:ro" \
  designer
```

A real catalogue is never committed to this repository — it is public, and an
institution's person-data field structure does not belong in it.

## Behind a path prefix

When served under `/portale/pass-designer`, set `PASS_DESIGNER_ROOT_PATH` to
the same prefix that Traefik strips. Both values must come from one variable in
the deployment, or the OpenAPI document advertises paths that do not answer.
````

- [ ] **Step 10: Commit**

```bash
make lint && make test-local
git add src/edutap/pass_designer/settings.py src/edutap/pass_designer/web \
        Dockerfile compose.yml docs/how-to/run-the-service.md tests/web
git commit -m "feat: expose the designer over http and ship a container"
```

---

## What this plan leaves for the next ones

**Plan 2 — the editor.** React, Vite and TanStack Query against the routes
above; the three view tabs with the module list outside them; the live preview
with `@bwip-js/browser`; the `@googleapis/walletobjects` wrapper module; the
generated TypeScript types; Vite's `base` tied to the Traefik prefix.

**Plan 3 — the remaining families.** Generic, then EventTicket, then GiftCard,
Offer, Transit and Flight. By then each is a descriptor and its
`required_on_create` set, written out from Google's REST reference — Transit and
Flight are the expensive two, because `FlightClass` needs `flightHeader`,
`origin` and `destination` as structures rather than text.

**Not planned here at all:** Apple and Samsung, writing to the manager over its
API, and image hosting through `edutap.image_service`.
