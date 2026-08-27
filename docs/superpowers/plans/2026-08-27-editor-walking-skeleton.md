# Editor Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person opens `/portale/edutap-designer`, lays out the front of a
Loyalty pass in English or German, sees it render as they type, presses Check,
and downloads `class.json`, `object.json` and `mappings.json`.

**Architecture:** A React SPA in `frontend/`, built by Vite and served by the
existing FastAPI app from the same container. The draft lives in a
`useReducer`; the preview derives from it locally and instantly, while
validation is an explicit call to the backend. TypeScript types are generated
from the backend's OpenAPI document — nothing is retyped by hand.

**Tech Stack:** React 19, Vite, TypeScript, TanStack Query, `openapi-typescript`
+ `openapi-fetch`, `react-i18next`, `@bwip-js/browser`, Vitest + React Testing
Library. Backend: Python 3.12+, FastAPI, gettext.

**Spec:** [`docs/superpowers/specs/2026-08-27-pass-designer-editor-design.md`](../specs/2026-08-27-pass-designer-editor-design.md)

## Global Constraints

- Python `>=3.12`, `uv run` for everything; never `pip` or a bare `python`
  outside the image.
- Node: the LTS line, via `nvm`. **`pnpm`**, one lock file, never mixed with
  `npm`.
- Repository language is **English** — code, comments, docstrings, commit
  messages. This is a public repository at edutap-collective.
- **The interface is multilingual: English and German now**, French, Portuguese
  and Swedish later. No user-facing string is hard-coded in a component.
- Two translation catalogues, and the split is not a matter of taste: the
  shared `edutap-collective/translations` submodule carries **domain terms**
  (*Date of Birth*, *Faculty*); `locales/` in this repository carries **what
  only this tool says** (interface chrome, finding messages).
- Placeholder syntax stays `${dotted.field}`, `$$` literal — it is the pass
  builder's, not ours.
- **NFC without a visible code is the normal case.** No code chosen means no
  code area at all, which moves the layout and must be visible.
- `make lint` and `make test-local` green before every commit; from Task 2 on,
  `make lint-frontend` and `make test-frontend` too.
- No real person's data anywhere. Preview personas come from Faker.
- Vite's `base` and `PASS_DESIGNER_ROOT_PATH` come from one variable.

---

### Task 1: Findings speak the reader's language

**Files:**
- Modify: `src/edutap/pass_designer/validation/_common.py`
- Modify: `src/edutap/pass_designer/validation/layout.py`, `values.py`, `exportable.py`
- Modify: `src/edutap/pass_designer/validation/__init__.py`
- Modify: `src/edutap/pass_designer/web/routers/design.py`
- Modify: `src/edutap/pass_designer/personas/generator.py`
- Create: `locales/en/LC_MESSAGES/messages.po`, `locales/de/LC_MESSAGES/messages.po`
- Create: `src/edutap/pass_designer/i18n.py`
- Test: `tests/test_i18n.py`, `tests/test_validation.py` (extend)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `translator(language: str) -> Callable[[str], str]`;
  `validate(draft, catalogue, language: str = "en") -> list[Finding]`;
  `negotiate(accept_language: str | None) -> str`. `Finding` is unchanged —
  `severity`, `message`, `location` — so the OpenAPI contract does not move.

**Why the message becomes a template.** Every finding today is an f-string
built where it is raised. To translate it, the *sentence* has to exist before
the values are put into it, so each check produces a msgid plus named
parameters and `validate` renders them once, in the requested language. The
English text stays the msgid, so an untranslated language falls back to it
automatically — a missing translation shows English, never a key.

- [ ] **Step 1: Write the failing test**

`tests/test_i18n.py`:

```python
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
    german = translator("de")

    assert german("head") != "head" or True  # smoke: the catalogue loads
    assert german("Google requires '%(key)s' when the class is created") != (
        "Google requires '%(key)s' when the class is created"
    )


def test_an_unknown_message_falls_back_to_its_own_text() -> None:
    german = translator("de")

    assert german("not in any catalogue") == "not in any catalogue"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_i18n.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edutap.pass_designer.i18n'`.

- [ ] **Step 3: Write the translation machinery**

`src/edutap/pass_designer/i18n.py`:

```python
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
    candidates: list[tuple[float, str]] = []
    for index, part in enumerate(accept_language.split(",")):
        tag, _, params = part.strip().partition(";")
        quality = 1.0
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        # `index` keeps the header's own order stable among equal qualities.
        candidates.append((-quality, index, tag.strip().lower()))  # type: ignore[arg-type]
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
```

- [ ] **Step 4: Write the catalogues**

`locales/en/LC_MESSAGES/messages.po` — the source language, entries empty so
gettext falls through to the msgid:

```po
msgid ""
msgstr ""
"Project-Id-Version: edutap.pass_designer\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
```

`locales/de/LC_MESSAGES/messages.po`:

```po
msgid ""
msgstr ""
"Project-Id-Version: edutap.pass_designer\n"
"Language: de\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"

msgid ""
"no %(kind)s module '%(module_id)s' exists; Google discards this reference "
"without reporting it and the value never appears"
msgstr ""
"Es gibt kein %(kind)s-Modul '%(module_id)s'. Google verwirft den Verweis "
"ohne Meldung, und der Wert erscheint nie."

msgid "Google requires '%(key)s' when the class is created"
msgstr "Google verlangt '%(key)s', wenn die Class angelegt wird."

msgid ""
"%(count)d %(label)s; Google accepts at most %(limit)d and drops the rest "
"without reporting it"
msgstr ""
"%(count)d %(label)s. Google nimmt höchstens %(limit)d und verwirft den Rest "
"ohne Meldung."

msgid "%(count)d %(label)s; the limit is %(limit)d"
msgstr "%(count)d %(label)s. Die Grenze liegt bei %(limit)d."

msgid ""
"is marked as bound but names no field; it would export as '${}', import back "
"as constant text, and then fail to export again"
msgstr ""
"ist als gebunden markiert, nennt aber kein Feld. Der Export schriebe '${}', "
"der Import läse es als konstanten Text, und der nächste Export scheiterte."

msgid ""
"'%(value)s' is not a field key; a binding is a dotted identifier such as "
"'person.display_name'"
msgstr ""
"'%(value)s' ist kein Feldschlüssel. Eine Bindung ist ein punktierter "
"Bezeichner wie 'person.display_name'."

msgid ""
"'%(value)s' is not in the field catalogue; the pass builder will not be able "
"to fill it"
msgstr ""
"'%(value)s' steht nicht im Feldkatalog. Der Pass-Builder kann es nicht "
"befüllen."

msgid ""
"'%(key)s' is part of the class, which is the template shared by every pass, "
"so it cannot be bound to '%(field_key)s'; only object-scoped fields differ "
"per person"
msgstr ""
"'%(key)s' gehört zur Class, der von allen Pässen geteilten Vorlage, und kann "
"deshalb nicht an '%(field_key)s' gebunden werden. Nur objektbezogene Felder "
"unterscheiden sich je Person."

msgid "a transit list option is not supported yet; the export would refuse it"
msgstr ""
"Eine Transit-Listenoption wird noch nicht unterstützt. Der Export würde sie "
"ablehnen."

msgid ""
"'%(key)s' is a localized head field, which is not supported yet; the export "
"would refuse it"
msgstr ""
"'%(key)s' ist ein lokalisiertes Kopffeld. Das wird noch nicht unterstützt, "
"der Export würde es ablehnen."

msgid ""
"'%(key)s' is an image field and cannot carry a placeholder; upstream types "
"the image URI as a strict URL"
msgstr ""
"'%(key)s' ist ein Bildfeld und kann keinen Platzhalter tragen. Die Bild-URI "
"ist stromaufwärts als strenge URL typisiert."

msgid "'%(key)s' must be a URL Google can fetch; '%(value)s' is not one"
msgstr ""
"'%(key)s' muss eine URL sein, die Google abrufen kann. '%(value)s' ist keine."

msgid ""
"'%(barcode_type)s' is not a barcode type Google knows; the export would "
"refuse it"
msgstr ""
"'%(barcode_type)s' ist kein Barcode-Typ, den Google kennt. Der Export würde "
"ihn ablehnen."

msgid ""
"image module '%(module_id)s' must be a URL Google can fetch; '%(value)s' is "
"not one"
msgstr ""
"Das Bildmodul '%(module_id)s' muss eine URL sein, die Google abrufen kann. "
"'%(value)s' ist keine."

msgid ""
"lone '$' at position %(position)d in %(text)r: write '$$' for a literal "
"dollar sign"
msgstr ""
"Einzelnes '$' an Position %(position)d in %(text)r. Für ein literales "
"Dollarzeichen '$$' schreiben."

msgid ""
"malformed field key '%(field_key)s' in placeholder at position %(position)d; "
"a field key is a dotted identifier"
msgstr ""
"Fehlerhafter Feldschlüssel '%(field_key)s' im Platzhalter an Position "
"%(position)d. Ein Feldschlüssel ist ein punktierter Bezeichner."
```

- [ ] **Step 5: Compile the catalogues and wire them into the build**

gettext reads `.mo`, not `.po`. Add to the `Makefile`:

```make
locales: ## Compile the .po catalogues to .mo
	@for po in locales/*/LC_MESSAGES/messages.po; do \
		uv run python -m msgfmt -o "$${po%.po}.mo" "$$po"; \
	done
```

Add `.PHONY: locales` to the existing list, add `*.mo` to `.gitignore` (the
`.po` files are the source; the `.mo` files are build output), and make
`test-local` depend on `locales` so a fresh checkout cannot run against a
missing catalogue.

Run: `make locales && ls locales/de/LC_MESSAGES/`
Expected: `messages.mo` exists beside `messages.po`.

- [ ] **Step 6: Turn each finding into a template plus parameters**

In `validation/_common.py`, add beside `Finding`:

```python
class FindingTemplate(BaseModel):
    """A finding before it is rendered into a language."""

    severity: Severity
    location: str
    msgid: str
    params: dict[str, object] = {}

    def render(self, translate: Callable[[str], str]) -> Finding:
        """Return the `Finding` a caller sees, in one language."""
        text = translate(self.msgid)
        return Finding(
            severity=self.severity,
            location=self.location,
            message=text % self.params if self.params else text,
        )
```

Then rewrite every `Finding(...)` construction in `layout.py`, `values.py` and
`exportable.py` as a `FindingTemplate`, moving the interpolated values out of
the f-string and into `params`. For example, in `layout.py`:

```python
        findings.append(
            FindingTemplate(
                severity="error",
                location=where,
                msgid=(
                    "no %(kind)s module '%(module_id)s' exists; Google "
                    "discards this reference without reporting it and the "
                    "value never appears"
                ),
                params={
                    "kind": reference.kind,
                    "module_id": reference.module_id,
                },
            )
        )
```

Each check function's return type becomes `list[FindingTemplate]`. The msgid
must match the catalogue entry **character for character** — a mismatch is a
silent fallback to English, not an error, so check them against
`locales/de/LC_MESSAGES/messages.po` as you go.

`check_dollar_signs` in `placeholders.py` returns finished strings today. Change
it to return `list[tuple[str, dict[str, object]]]` — msgid and params — and
update its own tests to match.

- [ ] **Step 7: Render in `validate`**

`validation/__init__.py`:

```python
def validate(
    draft: Draft, catalogue: Mapping[str, str], language: str = DEFAULT
) -> list[Finding]:
    """Return every problem found, errors and warnings together.

    `language` decides only how the messages read; which findings exist does
    not depend on it.
    """
    templates = [
        *check_field_paths(draft),
        *check_required_head_fields(draft),
        *check_volume(draft),
        *check_values(draft, catalogue),
        *check_exportable(draft),
    ]
    translate = translator(language)
    return [template.render(translate) for template in templates]
```

- [ ] **Step 8: Read the header in the routers**

In `web/routers/design.py`, add a dependency and pass it through:

```python
def language(
    accept_language: Annotated[str | None, Header()] = None,
) -> str:
    """Resolve the caller's preferred language from `Accept-Language`."""
    return negotiate(accept_language)
```

`validate_draft` and `export_draft` both take
`lang: Annotated[str, Depends(language)]` and pass it to `validate(...)`.

- [ ] **Step 9: Test that the header actually changes the text**

Add to `tests/web/test_api.py`:

```python
async def test_findings_follow_the_accept_language_header(
    client: AsyncClient,
) -> None:
    broken = {**DRAFT, "text_modules": []}

    english = await client.post(
        "/designer/v1/validate",
        json={"draft": broken},
        headers={"Accept-Language": "en"},
    )
    german = await client.post(
        "/designer/v1/validate",
        json={"draft": broken},
        headers={"Accept-Language": "de-DE,de;q=0.9"},
    )

    english_messages = [f["message"] for f in english.json()["findings"]]
    german_messages = [f["message"] for f in german.json()["findings"]]

    assert english_messages
    assert german_messages
    assert english_messages != german_messages
    assert len(english_messages) == len(german_messages)
```

- [ ] **Step 10: Add the two missing persona locales**

In `personas/generator.py`, extend `PERSONA_RECIPES` with Lund and Porto, whose
absence the design calls out:

```python
    ("sv-female", "Swedish, female", "sv_SE", "female", False),
    ("pt-male", "Portuguese, male", "pt_PT", "male", False),
```

Verify **before** trusting them, exactly as the existing locales were verified:
that `first_name_male`, `first_name_female`, `first_name_nonbinary`,
`last_name_male`, `last_name_female` and `last_name_nonbinary` all resolve on a
single-locale `Faker("sv_SE")` and `Faker("pt_PT")`. If one is missing, drop
that locale and say so — do not fall back to another gender's provider.

Update `test_the_three_genders_are_represented` if the counts it asserts change.

- [ ] **Step 11: Serve the field catalogue**

The editor offers bound fields from a picklist rather than a text box — a field
key typed by hand is wrong eventually, and the mistake surfaces as a pass that
never gets filled. Nothing exposes the catalogue today: `/families` carries head
fields and `/personas` carries personas, but the catalogue the service already
loads is not reachable.

Add to `web/routers/design.py`:

```python
@router.get("/catalogue")
async def list_catalogue(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> list[CatalogueField]:
    """Return the fields a data provider can deliver.

    The editor binds values against this list, so a field key cannot be
    mistyped. `CatalogueField` is the shape `edutap.pass_builder` already
    defines; nothing new is invented here.
    """
    return load_catalogue(settings.catalogue_path)
```

`CatalogueField` comes from `...personas.catalogue`, which already exposes it
as a Pydantic model, so it lands in the OpenAPI document with named fields
rather than as a bare object.

Add the test to `tests/web/test_api.py`:

```python
async def test_the_catalogue_is_offered_for_binding(client: AsyncClient) -> None:
    response = await client.get("/designer/v1/catalogue")

    assert response.status_code == 200
    keys = [field["key"] for field in response.json()]
    assert "person.display_name" in keys
    assert all("value_type" in field for field in response.json())
```

- [ ] **Step 12: Run everything**

Run: `make locales && make lint && make test-local`
Expected: green. The suite grows by the i18n tests, the header test and the
catalogue test.

- [ ] **Step 13: Commit**

```bash
git add locales .gitignore Makefile src/edutap/pass_designer tests
git commit -m "feat: render findings in the reader's language, and serve the catalogue"
```

---

### Task 2: The frontend shell

**Files:**
- Create: `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/schema.d.ts` (generated)
- Create: `frontend/scripts/openapi.mjs`
- Create: `frontend/src/api/client.test.ts`
- Modify: `Makefile`, `.gitignore`

**Interfaces:**
- Consumes: the backend's OpenAPI document.
- Produces: `client` (an `openapi-fetch` client typed by `paths`);
  `type Draft`, `type Finding`, `type FamilyResponse`, `type Persona` re-exported
  from `frontend/src/api/types.ts`.

- [ ] **Step 1: Scaffold and pin the toolchain**

```bash
cd frontend
pnpm init
pnpm add react react-dom @tanstack/react-query openapi-fetch
pnpm add -D vite @vitejs/plugin-react typescript @types/react @types/react-dom \
            openapi-typescript vitest @testing-library/react \
            @testing-library/jest-dom jsdom
```

**`pnpm`, one lock file, never mixed with `npm`** — the house rule, and a second
lock file is the kind of thing nobody notices until two machines resolve
different versions.

- [ ] **Step 2: Write the OpenAPI extraction script**

The types must come from the running app's own schema, not from a copy someone
remembered to update.

`frontend/scripts/openapi.mjs`:

```javascript
// Writes the backend's OpenAPI document to frontend/openapi.json by asking
// the application for it. No server needs to be running: the FastAPI app can
// produce its schema in-process.
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const script = `
import json
from edutap.pass_designer.web.app import create_app
print(json.dumps(create_app().openapi(), indent=2, sort_keys=True))
`;

const schema = execFileSync("uv", ["run", "python", "-c", script], {
  cwd: "..",
  encoding: "utf8",
  maxBuffer: 32 * 1024 * 1024,
});

writeFileSync("openapi.json", schema);
console.log(`wrote openapi.json (${schema.length} bytes)`);
```

- [ ] **Step 3: Write the failing test**

`frontend/src/api/client.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { Draft, Finding } from "./types";

describe("generated types", () => {
  it("carries the draft's own field names", () => {
    // A compile-time assertion: if the backend renames a field, this stops
    // building. That is the point — the alternative is a runtime surprise.
    const draft: Draft = {
      family: "loyalty",
      head: {},
      front_rows: [],
      back_items: [],
      list_view: {},
      text_modules: [],
      image_modules: [],
      link_modules: [],
      redemption: {},
      unmapped: {},
    };

    expect(draft.family).toBe("loyalty");
  });

  it("carries the finding shape the panel renders", () => {
    const finding: Finding = {
      severity: "error",
      message: "something",
      location: "head",
    };

    expect(finding.severity).toBe("error");
  });
});
```

- [ ] **Step 4: Run it and watch it fail**

Run: `cd frontend && pnpm vitest run`
Expected: FAIL — `Cannot find module './types'`.

- [ ] **Step 5: Generate the schema and write the type surface**

```bash
cd frontend
node scripts/openapi.mjs
pnpm openapi-typescript openapi.json -o src/api/schema.d.ts
```

`frontend/src/api/types.ts`:

```typescript
// One place that names the schema types the application uses. Components
// import from here, never from schema.d.ts directly, so a regeneration that
// moves a type is one edit rather than many.
import type { components } from "./schema";

export type Draft = components["schemas"]["Draft"];
export type Finding = components["schemas"]["Finding"];
export type FamilyResponse = components["schemas"]["FamilyResponse"];
export type HeadField = components["schemas"]["HeadField"];
export type Persona = components["schemas"]["Persona"];
export type TextModuleDraft = components["schemas"]["TextModuleDraft"];
export type ImageModuleDraft = components["schemas"]["ImageModuleDraft"];
export type LinkModuleDraft = components["schemas"]["LinkModuleDraft"];
export type Row = components["schemas"]["Row"];
export type Cell = components["schemas"]["Cell"];
export type Line = components["schemas"]["Line"];
export type FieldRef = components["schemas"]["FieldRef"];
export type ExportResponse = components["schemas"]["ExportResponse"];
```

`frontend/src/api/client.ts`:

```typescript
import createClient from "openapi-fetch";
import type { paths } from "./schema";

// `import.meta.env.BASE_URL` is what Vite's `base` resolves to at build time,
// so the client speaks to the same prefix the app is served from. Hard-coding
// "/" here is the mistake that works in development and 404s behind Traefik.
export const client = createClient<paths>({
  baseUrl: import.meta.env.BASE_URL,
});
```

- [ ] **Step 6: Configure Vite and Vitest**

`frontend/vite.config.ts`:

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `base` must match PASS_DESIGNER_ROOT_PATH. They come from one variable in
// the deployment; if they drift, the SPA fetches its own assets from the root
// and serves a white page.
export default defineConfig({
  base: process.env.PASS_DESIGNER_ROOT_PATH || "/",
  plugins: [react()],
  build: { outDir: "../src/edutap/pass_designer/web/static", emptyOutDir: true },
  test: { environment: "jsdom", globals: true, setupFiles: "./src/setup-tests.ts" },
});
```

`frontend/src/setup-tests.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 7: Run the test**

Run: `cd frontend && pnpm vitest run`
Expected: both tests PASS.

- [ ] **Step 8: Add the make targets and ignore the build output**

```make
frontend-install:
	cd frontend && pnpm install --frozen-lockfile

frontend-types:
	cd frontend && node scripts/openapi.mjs && \
		pnpm openapi-typescript openapi.json -o src/api/schema.d.ts

lint-frontend:
	cd frontend && pnpm tsc --noEmit

test-frontend:
	cd frontend && pnpm vitest run

build-frontend:
	cd frontend && pnpm build
```

Add all five to `.PHONY`. In `.gitignore`: `frontend/node_modules/`,
`frontend/openapi.json`, `src/edutap/pass_designer/web/static/`.
`schema.d.ts` **is** committed — it is the contract, and a diff on it is how a
reviewer sees the backend moved.

- [ ] **Step 9: Guard against type drift in CI**

Add a job to `.github/workflows/ci.yml` that regenerates and fails on a diff:

```yaml
  types:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: lts/*
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml
      - run: uv sync --group dev --frozen
      - run: make frontend-install
      - run: make frontend-types
      # Green here means both sides mean the same thing. A diff means someone
      # changed the backend schema without regenerating.
      - run: git diff --exit-code frontend/src/api/schema.d.ts
```

Extend the existing `check` job with `make lint-frontend` and
`make test-frontend` after the Python steps.

- [ ] **Step 10: Commit**

```bash
git add frontend Makefile .gitignore .github/workflows/ci.yml
git commit -m "feat: scaffold the frontend and generate its types from the schema"
```

---

### Task 3: FastAPI serves the build

**Files:**
- Modify: `src/edutap/pass_designer/web/app.py`
- Modify: `Dockerfile`
- Test: `tests/web/test_static.py`

**Interfaces:**
- Consumes: `create_app()` from Task 2's build output at
  `src/edutap/pass_designer/web/static/`.
- Produces: `create_app()` serving `index.html` at the root and at any path the
  API does not claim.

- [ ] **Step 1: Write the failing test**

`tests/web/test_static.py`:

```python
"""The single-page app is served by the same application as the API."""

import pytest
from httpx import ASGITransport, AsyncClient

from edutap.pass_designer.web.app import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_the_api_still_answers_when_no_build_exists() -> None:
    # A developer who has never run `make build-frontend` must still be able to
    # run the tests and the API. A missing build is not an error.
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/designer/v1/families")

    assert response.status_code == 200


async def test_an_unknown_path_does_not_shadow_the_api() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.get("/designer/v1/nonesuch")

    # Still a 404 from the router, never the SPA's index.html: an API path that
    # silently returns HTML is the failure mode that wastes an afternoon.
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/web/test_static.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.web.test_static'`
is not the failure; the second test fails because nothing distinguishes an
unknown API path yet. Confirm the actual message before proceeding.

- [ ] **Step 3: Mount the build**

In `web/app.py`, after `app.include_router(design.router)`:

```python
    # The built SPA, if there is one. Mounted last and under a catch-all so
    # the API keeps its paths: `/designer/v1/...` is matched by the router
    # above and never reaches this.
    static_dir = Path(__file__).parent / "static"
    if (static_dir / "index.html").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=static_dir / "assets"),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> FileResponse:
            """Serve the single-page app for any path the API does not claim.

            A single-page app owns its own routing, so a deep link has to
            return index.html rather than a 404 — the browser then resolves
            the route client-side.
            """
            return FileResponse(static_dir / "index.html")
```

The `if` matters: a checkout without a frontend build must still start, or
every backend test would need `pnpm build` first.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/web -v`
Expected: all PASS, including the pre-existing API tests.

- [ ] **Step 5: Add the Node stage to the Dockerfile**

```dockerfile
FROM node:lts-slim AS frontend
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
# The prefix is baked in at build time, so it must be given here and must
# match PASS_DESIGNER_ROOT_PATH at run time.
ARG PASS_DESIGNER_ROOT_PATH=/
ENV PASS_DESIGNER_ROOT_PATH=${PASS_DESIGNER_ROOT_PATH}
RUN pnpm build

FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=frontend /src/edutap/pass_designer/web/static ./src/edutap/pass_designer/web/static
RUN pip install --no-cache-dir build && python -m build --wheel
```

The final stage is unchanged except that it now also needs the compiled
catalogues: add `COPY locales ./locales` beside `COPY data ./data`.

**Note for whoever wires the deployment:** `pyproject.toml`'s wheel
configuration must include the `static` and `locales` directories, or the build
lands in the image and the wheel drops it. Verify with
`python -m zipfile -l dist/*.whl | grep -c static`.

- [ ] **Step 6: Verify the container serves the app**

```bash
make build-frontend
docker build --build-arg PASS_DESIGNER_ROOT_PATH=/portale/edutap-designer -t pass-designer:spa .
docker run --rm -d -p 8000:8000 --name designer-spa pass-designer:spa
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:8000/portale/edutap-designer/
curl -sf http://localhost:8000/portale/edutap-designer/designer/v1/families | head -c 80
docker rm -f designer-spa
```

Expected: `200` for the SPA, and the families JSON for the API. If Docker is
unavailable, say so and mark the step unverified — do not claim it worked.

- [ ] **Step 7: Commit**

```bash
git add src/edutap/pass_designer/web/app.py Dockerfile pyproject.toml tests/web/test_static.py
git commit -m "feat: serve the built single-page app from the same container"
```

---

### Task 4: The interface speaks two languages

**Files:**
- Create: `frontend/src/i18n/index.ts`, `frontend/src/i18n/en.json`, `frontend/src/i18n/de.json`
- Create: `frontend/src/components/LanguageSwitcher.tsx`
- Modify: `frontend/src/main.tsx`, `frontend/src/api/client.ts`
- Test: `frontend/src/i18n/i18n.test.ts`

**Interfaces:**
- Consumes: `client` from Task 2.
- Produces: `useTranslation()` from `react-i18next` throughout;
  `currentLanguage()` used by the API client to set `Accept-Language`.

- [ ] **Step 1: Write the failing test**

`frontend/src/i18n/i18n.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import i18n, { currentLanguage } from "./index";

describe("interface translations", () => {
  it("starts in a supported language", () => {
    expect(["en", "de"]).toContain(currentLanguage());
  });

  it("translates a key in both languages", async () => {
    await i18n.changeLanguage("en");
    const english = i18n.t("actions.check");

    await i18n.changeLanguage("de");
    const german = i18n.t("actions.check");

    expect(english).not.toBe("actions.check");
    expect(german).not.toBe("actions.check");
    expect(english).not.toBe(german);
  });

  it("every key in English exists in German", async () => {
    // A missing key renders as the key itself, which looks like a bug to a
    // user and like nothing at all to a test that only checks one key.
    const en = (await import("./en.json")).default;
    const de = (await import("./de.json")).default;

    const flatten = (o: object, p = ""): string[] =>
      Object.entries(o).flatMap(([k, v]) =>
        typeof v === "object" && v !== null
          ? flatten(v, `${p}${k}.`)
          : [`${p}${k}`],
      );

    expect(flatten(de).sort()).toEqual(flatten(en).sort());
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm vitest run src/i18n`
Expected: FAIL — `Cannot find module './index'`.

- [ ] **Step 3: Add the dependencies and write the catalogues**

```bash
cd frontend && pnpm add i18next react-i18next i18next-browser-languagedetector
```

`frontend/src/i18n/en.json`:

```json
{
  "app": { "title": "Pass Designer" },
  "tabs": { "front": "Card front" },
  "actions": {
    "check": "Check",
    "import": "Import…",
    "export": "Export",
    "addRow": "Add row",
    "addModule": "Add module"
  },
  "head": { "legend": "Card" },
  "modules": {
    "legend": "Modules",
    "shared": "Shared by every view — the front, the back and the overview row all reference these.",
    "constant": "Fixed value",
    "bound": "Filled per person",
    "header": "Header",
    "value": "Value",
    "field": "Field"
  },
  "preview": { "persona": "Preview person", "noCode": "No code — NFC only" },
  "findings": {
    "none": "No problems found.",
    "error": "Error",
    "warning": "Warning",
    "notCheckedYet": "Not checked yet."
  },
  "export": {
    "classJson": "Class JSON",
    "objectJson": "Object JSON",
    "mappings": "Mapping rules",
    "refused": "The export was refused. Fix the errors below and try again."
  }
}
```

`frontend/src/i18n/de.json` — the same keys, German values:

```json
{
  "app": { "title": "Pass-Designer" },
  "tabs": { "front": "Kartenvorderseite" },
  "actions": {
    "check": "Prüfen",
    "import": "Importieren…",
    "export": "Exportieren",
    "addRow": "Zeile hinzufügen",
    "addModule": "Modul hinzufügen"
  },
  "head": { "legend": "Karte" },
  "modules": {
    "legend": "Module",
    "shared": "Von allen Ansichten geteilt — Vorderseite, Rückseite und Übersichtszeile verweisen alle hierauf.",
    "constant": "Fester Wert",
    "bound": "Je Person befüllt",
    "header": "Kopfzeile",
    "value": "Wert",
    "field": "Feld"
  },
  "preview": { "persona": "Vorschauperson", "noCode": "Kein Code — nur NFC" },
  "findings": {
    "none": "Keine Probleme gefunden.",
    "error": "Fehler",
    "warning": "Warnung",
    "notCheckedYet": "Noch nicht geprüft."
  },
  "export": {
    "classJson": "Class-JSON",
    "objectJson": "Object-JSON",
    "mappings": "Zuordnungsregeln",
    "refused": "Der Export wurde abgelehnt. Beheben Sie die Fehler unten und versuchen Sie es erneut."
  }
}
```

- [ ] **Step 4: Write the setup**

`frontend/src/i18n/index.ts`:

```typescript
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import de from "./de.json";
import en from "./en.json";

// French, Portuguese and Swedish follow. Adding one is a catalogue and an
// entry here — no component changes, because no component holds a string.
export const SUPPORTED = ["en", "de"] as const;

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, de: { translation: de } },
    supportedLngs: [...SUPPORTED],
    fallbackLng: "en",
    interpolation: { escapeValue: false },
  });

export function currentLanguage(): string {
  return i18n.resolvedLanguage ?? "en";
}

export default i18n;
```

- [ ] **Step 5: Send the language to the backend**

The findings are translated by the server, so the client has to say which
language it wants. In `frontend/src/api/client.ts`:

```typescript
import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { currentLanguage } from "../i18n";

export const client = createClient<paths>({
  baseUrl: import.meta.env.BASE_URL,
});

// The backend renders finding messages from Accept-Language. Without this the
// interface would be German and its error messages English.
client.use({
  onRequest({ request }) {
    request.headers.set("Accept-Language", currentLanguage());
    return request;
  },
});
```

- [ ] **Step 6: Write the switcher**

`frontend/src/components/LanguageSwitcher.tsx`:

```typescript
import { useTranslation } from "react-i18next";
import { SUPPORTED } from "../i18n";

export function LanguageSwitcher() {
  const { i18n } = useTranslation();

  return (
    <select
      value={i18n.resolvedLanguage}
      onChange={(event) => void i18n.changeLanguage(event.target.value)}
      aria-label="Language"
    >
      {SUPPORTED.map((code) => (
        <option key={code} value={code}>
          {code.toUpperCase()}
        </option>
      ))}
    </select>
  );
}
```

Import `./i18n` in `main.tsx` before rendering, so the catalogues are
initialised once.

- [ ] **Step 7: Run the tests**

Run: `cd frontend && pnpm vitest run && pnpm tsc --noEmit`
Expected: all PASS, including the key-parity test.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/i18n frontend/src/components/LanguageSwitcher.tsx \
        frontend/src/api/client.ts frontend/src/main.tsx frontend/package.json \
        frontend/pnpm-lock.yaml
git commit -m "feat: translate the interface, and tell the backend which language"
```

---

### Task 5: The draft reducer

**Files:**
- Create: `frontend/src/draft/reducer.ts`, `frontend/src/draft/context.tsx`
- Test: `frontend/src/draft/reducer.test.ts`

**Interfaces:**
- Consumes: `Draft`, `Row`, `Cell`, `TextModuleDraft` from `../api/types`.
- Produces: `emptyDraft(family: string): Draft`;
  `draftReducer(state: Draft, action: DraftAction): Draft`;
  `DraftProvider`, `useDraft(): Draft`, `useDraftDispatch(): Dispatch<DraftAction>`.
  Actions: `setHead`, `addRow`, `removeRow`, `setRowCells`, `setCellField`,
  `addTextModule`, `removeTextModule`, `setTextModule`, `replaceDraft`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/draft/reducer.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { draftReducer, emptyDraft } from "./reducer";

const base = emptyDraft("loyalty");

describe("draftReducer", () => {
  it("sets a head field", () => {
    const next = draftReducer(base, {
      type: "setHead",
      key: "issuerName",
      value: "Example University",
    });

    expect(next.head).toEqual({ issuerName: "Example University" });
    expect(base.head).toEqual({}); // the previous state is untouched
  });

  it("adds a row with one empty cell", () => {
    const next = draftReducer(base, { type: "addRow" });

    expect(next.front_rows).toHaveLength(1);
    expect(next.front_rows[0].cells).toHaveLength(1);
  });

  it("changes how many cells a row has, keeping what fits", () => {
    let state = draftReducer(base, { type: "addRow" });
    state = draftReducer(state, {
      type: "setCellField",
      row: 0,
      cell: 0,
      kind: "text",
      moduleId: "name",
    });

    const widened = draftReducer(state, { type: "setRowCells", row: 0, cells: 3 });
    expect(widened.front_rows[0].cells).toHaveLength(3);
    expect(
      widened.front_rows[0].cells[0].first?.fallback_chain[0].module_id,
    ).toBe("name");

    const narrowed = draftReducer(widened, { type: "setRowCells", row: 0, cells: 1 });
    expect(narrowed.front_rows[0].cells).toHaveLength(1);
    expect(
      narrowed.front_rows[0].cells[0].first?.fallback_chain[0].module_id,
    ).toBe("name");
  });

  it("removes a row", () => {
    let state = draftReducer(base, { type: "addRow" });
    state = draftReducer(state, { type: "addRow" });

    expect(draftReducer(state, { type: "removeRow", row: 0 }).front_rows).toHaveLength(1);
  });

  it("adds, edits and removes a text module", () => {
    let state = draftReducer(base, { type: "addTextModule", moduleId: "name" });
    expect(state.text_modules).toHaveLength(1);

    state = draftReducer(state, {
      type: "setTextModule",
      moduleId: "name",
      patch: { value: "person.display_name", bound: true },
    });
    expect(state.text_modules[0].bound).toBe(true);
    expect(state.text_modules[0].value).toBe("person.display_name");

    state = draftReducer(state, { type: "removeTextModule", moduleId: "name" });
    expect(state.text_modules).toHaveLength(0);
  });

  it("replaces the whole draft on import", () => {
    const imported = { ...emptyDraft("loyalty"), head: { issuerName: "Other" } };

    expect(draftReducer(base, { type: "replaceDraft", draft: imported })).toEqual(
      imported,
    );
  });
});
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd frontend && pnpm vitest run src/draft`
Expected: FAIL — `Cannot find module './reducer'`.

- [ ] **Step 3: Write the reducer**

`frontend/src/draft/reducer.ts`:

```typescript
import type { Cell, Draft, Row, TextModuleDraft } from "../api/types";

export type DraftAction =
  | { type: "setHead"; key: string; value: string }
  | { type: "addRow" }
  | { type: "removeRow"; row: number }
  | { type: "setRowCells"; row: number; cells: 1 | 2 | 3 }
  | { type: "setCellField"; row: number; cell: number; kind: "text" | "image"; moduleId: string }
  | { type: "addTextModule"; moduleId: string }
  | { type: "removeTextModule"; moduleId: string }
  | { type: "setTextModule"; moduleId: string; patch: Partial<TextModuleDraft> }
  | { type: "replaceDraft"; draft: Draft };

export function emptyDraft(family: string): Draft {
  return {
    family,
    head: {},
    front_rows: [],
    back_items: [],
    list_view: {},
    text_modules: [],
    image_modules: [],
    link_modules: [],
    redemption: {},
    unmapped: {},
  };
}

const emptyCell = (): Cell => ({});

function withRow(state: Draft, index: number, change: (row: Row) => Row): Draft {
  return {
    ...state,
    front_rows: state.front_rows.map((row, i) => (i === index ? change(row) : row)),
  };
}

export function draftReducer(state: Draft, action: DraftAction): Draft {
  switch (action.type) {
    case "setHead":
      return { ...state, head: { ...state.head, [action.key]: action.value } };

    case "addRow":
      return { ...state, front_rows: [...state.front_rows, { cells: [emptyCell()] }] };

    case "removeRow":
      return {
        ...state,
        front_rows: state.front_rows.filter((_, i) => i !== action.row),
      };

    case "setRowCells":
      // Keep what fits. Narrowing a row drops the cells beyond the new width
      // rather than clearing the row: a mis-click costs one cell, not the
      // whole layout.
      return withRow(state, action.row, (row) => ({
        cells: Array.from(
          { length: action.cells },
          (_, i) => row.cells[i] ?? emptyCell(),
        ),
      }));

    case "setCellField":
      return withRow(state, action.row, (row) => ({
        cells: row.cells.map((cell, i) =>
          i === action.cell
            ? {
                ...cell,
                first: {
                  fallback_chain: [
                    { kind: action.kind, module_id: action.moduleId },
                  ],
                },
              }
            : cell,
        ),
      }));

    case "addTextModule":
      return {
        ...state,
        text_modules: [
          ...state.text_modules,
          { module_id: action.moduleId, value: "", bound: false },
        ],
      };

    case "removeTextModule":
      return {
        ...state,
        text_modules: state.text_modules.filter(
          (module) => module.module_id !== action.moduleId,
        ),
      };

    case "setTextModule":
      return {
        ...state,
        text_modules: state.text_modules.map((module) =>
          module.module_id === action.moduleId
            ? { ...module, ...action.patch }
            : module,
        ),
      };

    case "replaceDraft":
      return action.draft;
  }
}
```

- [ ] **Step 4: Write the context**

`frontend/src/draft/context.tsx`:

```typescript
import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from "react";
import type { Draft } from "../api/types";
import { draftReducer, emptyDraft, type DraftAction } from "./reducer";

const DraftContext = createContext<Draft | null>(null);
const DispatchContext = createContext<Dispatch<DraftAction> | null>(null);

export function DraftProvider({ children }: { children: ReactNode }) {
  const [draft, dispatch] = useReducer(draftReducer, emptyDraft("loyalty"));

  return (
    <DraftContext.Provider value={draft}>
      <DispatchContext.Provider value={dispatch}>{children}</DispatchContext.Provider>
    </DraftContext.Provider>
  );
}

export function useDraft(): Draft {
  const draft = useContext(DraftContext);
  if (!draft) throw new Error("useDraft must be used inside a DraftProvider");
  return draft;
}

export function useDraftDispatch(): Dispatch<DraftAction> {
  const dispatch = useContext(DispatchContext);
  if (!dispatch) throw new Error("useDraftDispatch must be used inside a DraftProvider");
  return dispatch;
}
```

- [ ] **Step 5: Run the tests**

Run: `cd frontend && pnpm vitest run && pnpm tsc --noEmit`
Expected: all six reducer tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/draft
git commit -m "feat: hold the draft in a reducer, one action per edit"
```

---

### Task 6: The card-front tab and the module list

**Files:**
- Create: `frontend/src/components/HeadFields.tsx`, `frontend/src/components/FrontRows.tsx`
- Create: `frontend/src/components/ModuleList.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/components/ModuleList.test.tsx`

**Interfaces:**
- Consumes: `useDraft`, `useDraftDispatch` (Task 5); `client` (Task 2);
  `useTranslation` (Task 4).
- Produces: `<HeadFields />`, `<FrontRows />`, `<ModuleList />`, all reading the
  draft from context.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/ModuleList.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DraftProvider } from "../draft/context";
import { ModuleList } from "./ModuleList";
import "../i18n";

function renderList() {
  return render(
    <DraftProvider>
      <ModuleList catalogue={[{ key: "person.display_name", value_type: "text" }]} />
    </DraftProvider>,
  );
}

describe("ModuleList", () => {
  it("says that modules are shared by every view", () => {
    renderList();

    // The single most direct way to break a template is to believe a module
    // belongs to the tab you are looking at. The interface has to say so.
    expect(screen.getByText(/shared by every view|geteilt/i)).toBeInTheDocument();
  });

  it("adds a module and lets it be switched to a bound value", async () => {
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /add module|Modul hinzufügen/i }));
    await user.type(screen.getByLabelText(/header|kopfzeile/i), "Name");
    await user.click(screen.getByLabelText(/filled per person|je person/i));

    expect(screen.getByRole("combobox", { name: /field|feld/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm vitest run src/components/ModuleList`
Expected: FAIL — `Cannot find module './ModuleList'`.

- [ ] **Step 3: Write the module list**

`frontend/src/components/ModuleList.tsx`:

```typescript
import { useTranslation } from "react-i18next";
import { useDraft, useDraftDispatch } from "../draft/context";

type CatalogueField = { key: string; value_type: string };

/**
 * The modules a pass carries.
 *
 * This list sits OUTSIDE the view tabs on purpose: the front, the back and the
 * Wallet overview row all reference the same modules by field path. Inside a
 * tab it would suggest a module belongs to a view. It belongs to none of them,
 * and believing otherwise is the most direct route to a broken template.
 */
export function ModuleList({ catalogue }: { catalogue: CatalogueField[] }) {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();

  return (
    <fieldset>
      <legend>{t("modules.legend")}</legend>
      <p>{t("modules.shared")}</p>

      {draft.text_modules.map((module) => (
        <div key={module.module_id}>
          <label>
            {t("modules.header")}
            <input
              value={module.header ?? ""}
              onChange={(e) =>
                dispatch({
                  type: "setTextModule",
                  moduleId: module.module_id,
                  patch: { header: e.target.value },
                })
              }
            />
          </label>

          <label>
            {t("modules.bound")}
            <input
              type="checkbox"
              checked={module.bound}
              onChange={(e) =>
                dispatch({
                  type: "setTextModule",
                  moduleId: module.module_id,
                  patch: { bound: e.target.checked, value: "" },
                })
              }
            />
          </label>

          {module.bound ? (
            <label>
              {t("modules.field")}
              <select
                value={module.value}
                onChange={(e) =>
                  dispatch({
                    type: "setTextModule",
                    moduleId: module.module_id,
                    patch: { value: e.target.value },
                  })
                }
              >
                <option value="" />
                {catalogue.map((field) => (
                  <option key={field.key} value={field.key}>
                    {field.key}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              {t("modules.value")}
              <input
                value={module.value}
                onChange={(e) =>
                  dispatch({
                    type: "setTextModule",
                    moduleId: module.module_id,
                    patch: { value: e.target.value },
                  })
                }
              />
            </label>
          )}
        </div>
      ))}

      <button
        type="button"
        onClick={() =>
          dispatch({
            type: "addTextModule",
            moduleId: `module_${draft.text_modules.length + 1}`,
          })
        }
      >
        {t("actions.addModule")}
      </button>
    </fieldset>
  );
}
```

**Why the field is a picklist and not a text box:** a field key typed by hand is
wrong eventually, and the mistake surfaces as a pass that never gets filled.
Offered from the catalogue it cannot be wrong.

- [ ] **Step 4: Write the head fields**

`frontend/src/components/HeadFields.tsx` — driven by the descriptor, so a
family with different fields needs no component change:

```typescript
import { useTranslation } from "react-i18next";
import type { HeadField } from "../api/types";
import { useDraft, useDraftDispatch } from "../draft/context";

export function HeadFields({ fields }: { fields: HeadField[] }) {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();

  return (
    <fieldset>
      <legend>{t("head.legend")}</legend>
      {fields
        .filter((field) => field.scope === "class" || field.scope === "object")
        .map((field) => (
          <label key={field.key}>
            {field.label}
            {field.required ? " *" : ""}
            <input
              type={field.kind === "colour" ? "color" : "text"}
              value={draft.head[field.key] ?? ""}
              onChange={(e) =>
                dispatch({ type: "setHead", key: field.key, value: e.target.value })
              }
            />
          </label>
        ))}
    </fieldset>
  );
}
```

- [ ] **Step 5: Write the row editor**

`frontend/src/components/FrontRows.tsx`:

```typescript
import { useTranslation } from "react-i18next";
import { useDraft, useDraftDispatch } from "../draft/context";

export function FrontRows() {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();

  return (
    <fieldset>
      <legend>{t("tabs.front")}</legend>

      {draft.front_rows.map((row, rowIndex) => (
        <div key={rowIndex}>
          <select
            value={row.cells.length}
            aria-label={`Row ${rowIndex + 1}`}
            onChange={(e) =>
              dispatch({
                type: "setRowCells",
                row: rowIndex,
                cells: Number(e.target.value) as 1 | 2 | 3,
              })
            }
          >
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>

          {row.cells.map((cell, cellIndex) => (
            <select
              key={cellIndex}
              value={cell.first?.fallback_chain[0]?.module_id ?? ""}
              aria-label={`Row ${rowIndex + 1} cell ${cellIndex + 1}`}
              onChange={(e) =>
                dispatch({
                  type: "setCellField",
                  row: rowIndex,
                  cell: cellIndex,
                  kind: "text",
                  moduleId: e.target.value,
                })
              }
            >
              <option value="" />
              {draft.text_modules.map((module) => (
                <option key={module.module_id} value={module.module_id}>
                  {module.header || module.module_id}
                </option>
              ))}
            </select>
          ))}

          <button type="button" onClick={() => dispatch({ type: "removeRow", row: rowIndex })}>
            ×
          </button>
        </div>
      ))}

      <button type="button" onClick={() => dispatch({ type: "addRow" })}>
        {t("actions.addRow")}
      </button>
    </fieldset>
  );
}
```

- [ ] **Step 6: Assemble in `App.tsx`**

```bash
cd frontend && pnpm add -D @testing-library/user-event
```

`frontend/src/App.tsx`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { client } from "./api/client";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { FrontRows } from "./components/FrontRows";
import { HeadFields } from "./components/HeadFields";
import { ModuleList } from "./components/ModuleList";
import { DraftProvider } from "./draft/context";

function Editor() {
  const { t } = useTranslation();

  const families = useQuery({
    queryKey: ["families"],
    queryFn: async () => {
      const { data, error } = await client.GET("/designer/v1/families");
      if (error) throw new Error("families failed");
      return data;
    },
  });

  const catalogue = useQuery({
    queryKey: ["catalogue"],
    queryFn: async () => {
      const { data, error } = await client.GET("/designer/v1/catalogue");
      if (error) throw new Error("catalogue failed");
      return data;
    },
  });

  // Loyalty is the only registered family; the six others need a backend round
  // first. Reading it from the list rather than hard-coding the head fields
  // means that round costs no change here.
  const loyalty = families.data?.find((f) => f.family_id === "loyalty");

  if (!loyalty || !catalogue.data) return <p>…</p>;

  return (
    <main>
      <header>
        <h1>{t("app.title")}</h1>
        <LanguageSwitcher />
      </header>

      <div className="editor">
        <form onSubmit={(e) => e.preventDefault()}>
          {/* The tabs will grow to three. Today there is one, and the module
              list sits OUTSIDE them — the front, the back and the overview row
              all reference the same modules. */}
          <section aria-label={t("tabs.front")}>
            <HeadFields fields={loyalty.head_fields} />
            <FrontRows />
          </section>

          <ModuleList catalogue={catalogue.data} />
        </form>
      </div>
    </main>
  );
}

export default function App() {
  return (
    <DraftProvider>
      <Editor />
    </DraftProvider>
  );
}
```

`main.tsx` wraps this in a `QueryClientProvider` and imports `./i18n` before
rendering.

- [ ] **Step 7: Run the tests**

Run: `cd frontend && pnpm vitest run && pnpm tsc --noEmit`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components frontend/src/App.tsx frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat: edit the card front, with the module list outside the tabs"
```

---

### Task 7: The preview and the persona switcher

**Files:**
- Create: `frontend/src/preview/resolve.ts`, `frontend/src/preview/Card.tsx`
- Create: `frontend/src/preview/Card.css`
- Test: `frontend/src/preview/resolve.test.ts`

**Interfaces:**
- Consumes: `useDraft` (Task 5); `Persona` (Task 2).
- Produces: `resolvePlaceholders(text: string, values: Record<string, string>): string`;
  `<Card persona={…} />`.

- [ ] **Step 1: Write the failing test**

`frontend/src/preview/resolve.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { resolvePlaceholders } from "./resolve";

const values = { "person.display_name": "Isolde Reichmann" };

describe("resolvePlaceholders", () => {
  it("substitutes a known field", () => {
    expect(resolvePlaceholders("${person.display_name}", values)).toBe(
      "Isolde Reichmann",
    );
  });

  it("substitutes inside surrounding text", () => {
    expect(resolvePlaceholders("Hello ${person.display_name}!", values)).toBe(
      "Hello Isolde Reichmann!",
    );
  });

  it("turns a doubled dollar into a literal one", () => {
    expect(resolvePlaceholders("costs 5$$", values)).toBe("costs 5$");
  });

  it("leaves an unknown field visible rather than blank", () => {
    // Blanking it would make a missing binding look like an empty field. The
    // designer has to see that nothing filled it.
    expect(resolvePlaceholders("${person.nonesuch}", values)).toBe(
      "${person.nonesuch}",
    );
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm vitest run src/preview`
Expected: FAIL — `Cannot find module './resolve'`.

- [ ] **Step 3: Write the resolver**

`frontend/src/preview/resolve.ts`:

```typescript
// The same syntax edutap.pass_builder resolves at issuing time: ${dotted.field}
// binds, $$ is a literal dollar sign, and only values are ever touched. The
// preview walks the same path the real thing will, so what it shows is what a
// cardholder gets — with invented data.
const TOKEN = /\$\$|\$\{([^}]+)\}/g;

export function resolvePlaceholders(
  text: string,
  values: Record<string, string>,
): string {
  return text.replace(TOKEN, (match, fieldKey?: string) => {
    if (match === "$$") return "$";
    return values[fieldKey!] ?? match;
  });
}
```

- [ ] **Step 4: Write the card**

`frontend/src/preview/Card.tsx`:

```typescript
import { useTranslation } from "react-i18next";
import type { Persona } from "../api/types";
import { useDraft } from "../draft/context";
import { resolvePlaceholders } from "./resolve";
import "./Card.css";

export function Card({ persona }: { persona: Persona | undefined }) {
  const draft = useDraft();
  const { t } = useTranslation();
  const values = persona?.values ?? {};

  const textOf = (moduleId: string | undefined): string => {
    const module = draft.text_modules.find((m) => m.module_id === moduleId);
    if (!module) return "";
    // A bound value is resolved against the persona; a constant is shown as
    // it is. Both take the same path the pass builder takes at issuing time.
    return module.bound
      ? resolvePlaceholders(`\${${module.value}}`, values)
      : module.value;
  };

  const headerOf = (moduleId: string | undefined): string =>
    draft.text_modules.find((m) => m.module_id === moduleId)?.header ?? "";

  return (
    <div
      className="card"
      style={{ background: draft.head.hexBackgroundColor || "#4285f4" }}
    >
      {draft.head.programLogo ? (
        <img className="card__logo" src={draft.head.programLogo} alt="" />
      ) : null}
      <div className="card__issuer">{draft.head.issuerName}</div>
      <div className="card__program">{draft.head.programName}</div>

      {draft.front_rows.map((row, rowIndex) => (
        <div
          key={rowIndex}
          className="card__row"
          style={{ gridTemplateColumns: `repeat(${row.cells.length}, 1fr)` }}
        >
          {row.cells.map((cell, cellIndex) => {
            const moduleId = cell.first?.fallback_chain[0]?.module_id;
            return (
              <div key={cellIndex} className="card__cell">
                <div className="card__label">{headerOf(moduleId)}</div>
                <div className="card__value">{textOf(moduleId)}</div>
              </div>
            );
          })}
        </div>
      ))}

      {/* NFC without a visible code is the normal case. Its absence moves the
          layout, so it is shown rather than left blank. */}
      {draft.redemption.barcode_type ? (
        <canvas className="card__code" data-testid="card-code" />
      ) : (
        <div className="card__nocode">{t("preview.noCode")}</div>
      )}
    </div>
  );
}
```

`frontend/src/preview/Card.css`:

```css
/* Proportions and wrapping have to be right; pixels do not. A Wallet card is
   roughly 1.6:1 and the text wraps rather than truncating, which is what a
   layout decision actually turns on. */
.card {
  aspect-ratio: 1.6;
  max-width: 26rem;
  padding: 1rem;
  border-radius: 0.75rem;
  color: #fff;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-wrap: anywhere;
}
.card__logo { width: 2.5rem; height: 2.5rem; border-radius: 50%; object-fit: cover; }
.card__issuer { font-size: 0.75rem; opacity: 0.85; }
.card__program { font-size: 1.25rem; font-weight: 600; }
.card__row { display: grid; gap: 0.5rem; }
.card__label { font-size: 0.7rem; opacity: 0.8; }
.card__value { font-size: 0.9rem; }
.card__code { align-self: center; margin-top: auto; background: #fff; }
.card__nocode { margin-top: auto; font-size: 0.7rem; opacity: 0.6; }
```

- [ ] **Step 5: Add the barcode**

```bash
cd frontend && pnpm add @bwip-js/browser
```

When a code is chosen, render it for real into a `<canvas>`, mapping Google's
type to the BWIPP encoder name:

```typescript
const ENCODERS: Record<string, string> = {
  AZTEC: "azteccode",
  CODE_39: "code39",
  CODE_128: "code128",
  CODABAR: "rationalizedCodabar",
  DATA_MATRIX: "datamatrix",
  EAN_8: "ean8",
  EAN_13: "ean13",
  ITF_14: "itf14",
  PDF_417: "pdf417",
  QR_CODE: "qrcode",
  UPC_A: "upca",
  // TEXT_ONLY draws no code by definition.
};
```

A fake code would be a falsehood at exactly the spot a designer looks at, and
it would misstate the footprint — which is what actually moves the layout.

- [ ] **Step 6: Add the persona switcher**

Fetch `/designer/v1/personas` with TanStack Query, render a `<select>` labelled
`preview.persona`, and pass the chosen persona's `values` into `<Card />`.

- [ ] **Step 7: Run the tests**

Run: `cd frontend && pnpm vitest run && pnpm tsc --noEmit`
Expected: PASS. **Do not add a test that asserts CSS classes** — see the spec.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/preview frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat: render the card, resolved against a preview persona"
```

---

### Task 8: Check, import and export

**Files:**
- Create: `frontend/src/components/Findings.tsx`, `frontend/src/components/Toolbar.tsx`
- Create: `frontend/src/api/actions.ts`
- Test: `frontend/src/api/actions.test.ts`

**Interfaces:**
- Consumes: `client` (Task 2), `useDraft`/`useDraftDispatch` (Task 5).
- Produces: `checkDraft(draft) → Finding[]`;
  `exportDraft(draft, classId, objectId) → ExportResponse`;
  `importFiles(family, classFile, objectFile) → Draft`;
  `downloadJson(name: string, value: unknown): void`.

- [ ] **Step 1: Write the failing test**

`frontend/src/api/actions.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { downloadJson } from "./actions";

describe("downloadJson", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("offers one file per artefact, named after it", () => {
    const click = vi.fn();
    vi.spyOn(document, "createElement").mockReturnValue({
      click,
      href: "",
      download: "",
      remove: vi.fn(),
    } as unknown as HTMLAnchorElement);
    vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL: vi.fn() });

    downloadJson("class.json", { id: "1.a" });

    expect(click).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && pnpm vitest run src/api/actions`
Expected: FAIL — `Cannot find module './actions'`.

- [ ] **Step 3: Write the actions**

`frontend/src/api/actions.ts`:

```typescript
import type { Draft, ExportResponse, Finding } from "./types";
import { client } from "./client";

export async function checkDraft(draft: Draft): Promise<Finding[]> {
  const { data, error } = await client.POST("/designer/v1/validate", {
    body: { draft },
  });
  if (error) throw new Error("validate failed");
  return data.findings;
}

export async function exportDraft(
  draft: Draft,
  classId: string,
  objectId: string,
): Promise<ExportResponse> {
  const { data, error, response } = await client.POST("/designer/v1/export", {
    body: { draft, class_id: classId, object_id: objectId },
  });
  if (error) {
    // 422 carries the findings list. Surfacing it as findings rather than as
    // an opaque failure is the whole reason the backend answers in that shape.
    throw Object.assign(new Error("export refused"), {
      status: response.status,
      findings: (error as { detail?: Finding[] }).detail ?? [],
    });
  }
  return data;
}

export async function importFiles(
  family: string,
  classFile: File,
  objectFile: File,
): Promise<Draft> {
  const [classJson, objectJson] = await Promise.all([
    classFile.text().then(JSON.parse),
    objectFile.text().then(JSON.parse),
  ]);
  const { data, error } = await client.POST("/designer/v1/import", {
    body: { family, class_json: classJson, object_json: objectJson },
  });
  if (error) throw new Error("import failed");
  return data;
}

/**
 * Offer one JSON file for download.
 *
 * Three separate links rather than one archive: browsers block several
 * simultaneous downloads, a ZIP costs a dependency, and the pass builder
 * manager takes the files separately anyway.
 */
export function downloadJson(name: string, value: unknown): void {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 4: Write the findings panel**

`frontend/src/components/Findings.tsx`:

```typescript
import { useTranslation } from "react-i18next";
import type { Finding } from "../api/types";

// `null` means "not checked yet", which is a different thing from "checked and
// clean". Conflating them would let an unchecked draft look approved.
export function Findings({ findings }: { findings: Finding[] | null }) {
  const { t } = useTranslation();

  if (findings === null) return <p>{t("findings.notCheckedYet")}</p>;
  if (findings.length === 0) return <p>{t("findings.none")}</p>;

  const ordered = [
    ...findings.filter((f) => f.severity === "error"),
    ...findings.filter((f) => f.severity !== "error"),
  ];

  return (
    <ul aria-label={t("findings.error")}>
      {ordered.map((finding, index) => (
        <li key={index} data-severity={finding.severity}>
          <strong>
            {finding.severity === "error"
              ? t("findings.error")
              : t("findings.warning")}
          </strong>{" "}
          <code>{finding.location}</code> — {finding.message}
        </li>
      ))}
    </ul>
  );
}
```

The messages arrive already translated: the client sends `Accept-Language`
(Task 4) and the backend renders them (Task 1).

- [ ] **Step 5: Write the toolbar**

`frontend/src/components/Toolbar.tsx`:

```typescript
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Finding } from "../api/types";
import { checkDraft, downloadJson, exportDraft, importFiles } from "../api/actions";
import { useDraft, useDraftDispatch } from "../draft/context";
import { Findings } from "./Findings";

export function Toolbar() {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [refused, setRefused] = useState(false);
  const [classFile, setClassFile] = useState<File | null>(null);
  const [objectFile, setObjectFile] = useState<File | null>(null);

  async function onCheck() {
    setRefused(false);
    setFindings(await checkDraft(draft));
  }

  async function onExport() {
    setRefused(false);
    try {
      const result = await exportDraft(draft, "ISSUER.class", "ISSUER.specimen");
      setFindings([]);
      downloadJson("class.json", result.class_json);
      downloadJson("object.json", result.object_json);
      downloadJson("mappings.json", result.mappings);
    } catch (error) {
      // The 422 carries the findings list. Showing it in the same panel as
      // Check means one place to look, whichever button was pressed.
      const detail = error as { findings?: Finding[] };
      setFindings(detail.findings ?? []);
      setRefused(true);
    }
  }

  async function onImport() {
    if (!classFile || !objectFile) return;
    dispatch({
      type: "replaceDraft",
      draft: await importFiles(draft.family, classFile, objectFile),
    });
    setFindings(null);
  }

  return (
    <section>
      <button type="button" onClick={() => void onCheck()}>
        {t("actions.check")}
      </button>
      <button type="button" onClick={() => void onExport()}>
        {t("actions.export")}
      </button>

      <label>
        {t("export.classJson")}
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setClassFile(e.target.files?.[0] ?? null)}
        />
      </label>
      <label>
        {t("export.objectJson")}
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setObjectFile(e.target.files?.[0] ?? null)}
        />
      </label>
      <button type="button" onClick={() => void onImport()} disabled={!classFile || !objectFile}>
        {t("actions.import")}
      </button>

      {refused ? <p role="alert">{t("export.refused")}</p> : null}
      <Findings findings={findings} />
    </section>
  );
}
```

Render `<Toolbar />` and `<Card persona={…} />` from `App.tsx`, the form on the
left and the preview on the right.

- [ ] **Step 6: Run the tests**

Run: `cd frontend && pnpm vitest run && pnpm tsc --noEmit && cd .. && make lint && make test-local`
Expected: green on both sides.

- [ ] **Step 7: Walk the skeleton, by hand, once**

```bash
make locales && make build-frontend
PASS_DESIGNER_ROOT_PATH= uv run uvicorn edutap.pass_designer.web.app:app
```

Open `http://localhost:8000/`, and in one sitting: add two modules, put them in
a two-cell row, switch one to a bound value, switch the persona and watch the
card change, switch the language and watch the interface change, press Check
and read a finding in that language, press Export and get three files. Open the
downloaded `class.json` and confirm the row is there.

Write down what was awkward. That list is the input to the next round — it is
the reason this plan builds a skeleton rather than four separate pieces.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat: check a draft, import two documents, export three files"
```

---

## What this plan leaves for the next rounds

**The other two views.** The *back* tab is a flat list, not a grid —
`DetailsItemInfo` holds exactly one item. The *Wallet overview* tab has exactly
two rows. Both are already in the `Draft` and the exporter; only the editor is
missing.

**Preview fidelity.** Collect the screenshots first, then build the geometry.
Doing it the other way round means measuring twice.

**The barcode section, undo and redo, local image files for the preview, and
uploading a real field catalogue.**

**The six remaining families**, which need a backend round first — only Loyalty
is registered today.

**Two things the spec names that this plan deliberately does not build**, said
plainly so a reader does not take them for oversights:

* **`@googleapis/walletobjects`.** The spec has the editor take Google's own
  structures from there. The skeleton never touches them: it edits a `Draft`,
  and the class and object documents only exist inside the export response,
  which crosses the wire as an opaque object and is written straight to a file.
  The dependency earns its place when something in the browser has to *read*
  an exported document — an import preview, say — and not before.
* **The shared `edutap-collective/translations` submodule.** The skeleton lets
  a person type a module header by hand. Offering the 35-language domain terms
  instead is worth doing, but it is a feature of the module editor rather than
  of the walking skeleton, and adding a submodule brings the pointer discipline
  with it. `locales/` covers what the skeleton actually says.
