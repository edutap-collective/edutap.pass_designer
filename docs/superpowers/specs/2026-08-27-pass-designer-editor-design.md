# Pass Designer Editor — Design

**Date:** 2026-08-27
**Status:** agreed, not yet implemented
**Follows:** [`2026-08-26-pass-designer-design.md`](2026-08-26-pass-designer-design.md)

A snapshot of the design as it stands on the date above. It is not rewritten
when the design changes; a changed decision gets a new document.

## What this is

The React editor that sits in front of the backend built in the previous
design. The backend is live: five routes under `/designer/v1`, 26 typed
schemas, 122 tests, deployed at `/portale/edutap-designer` behind Shibboleth
and MFA.

## Scope: a walking skeleton

The editor is four pieces that build on each other — shell, form, preview,
import/export. Building them as four separate rounds would mean three rounds
that produce nothing anyone can judge: a form without a preview and a preview
without an export are both untestable by eye.

So the first round is a **walking skeleton**: the shell, **one** tab (the card
front), a rough preview, and import and export working end to end. At the end
of it a person lays out a Loyalty pass and downloads the three files. It will
be ugly. It will be complete.

Everything else is a later round, deliberately:

* the *back* and *Wallet overview* tabs
* editing the barcode section
* undo and redo
* dropping a local image file for the preview
* uploading a real field catalogue
* the six remaining pass families — the backend registers only Loyalty today
* preview fidelity beyond "proportions and wrapping are right"

The point of stopping there is to learn whether the interaction model holds
before effort goes into polish.

## Serving and packaging

The SPA is served by FastAPI from the same container, through `StaticFiles`,
with a Node stage in the Dockerfile. The service already runs behind exactly
one route; a second container would be a second deployment for nothing.

**Vite's `base` and `PASS_DESIGNER_ROOT_PATH` come from one variable.** If they
drift, the SPA requests its own assets from the root and serves a white page —
the same failure the how-to already warns about for the OpenAPI document.

## Languages

The interface is multilingual from the first line: **English and German to
start, French, Portuguese and Swedish to follow.** eduTAP is a EUGLOH
collaboration; the partners in Lund, Porto and Paris-Saclay are the reason.

Translations live in **two catalogues, and the split is not a matter of taste**:

| | Source | Contents |
|---|---|---|
| Shared | `edutap-collective/translations`, as a submodule | Domain terms: *Date of Birth*, *Faculty*, *Employee ID*. 35 languages, already written. |
| Local | `locales/` in this repository | What only this tool says: interface chrome and the finding messages. |

A field label is something every eduTAP package says; a finding message is
something only this one says. Filling the shared catalogue with our error texts
would make it useless to its siblings.

The shared catalogue is a better fit than it first appears: its 22 entries are
exactly the headers a pass module carries, and Google's `LocalizedString` wants
them in exactly that shape. A module headed *Date of Birth* gets 35 languages
for free.

**Findings are translated by the backend**, keyed off `Accept-Language`:
gettext in the service, the local catalogue built into the image, and the
existing English `message` kept as the fallback when a language is missing.
Adding French, Portuguese and Swedish is then catalogue entries, not code.

This is backend work the editor cannot do for itself — see *Sequencing*.

## State and data flow

The `Draft` lives in a `useReducer` behind a context; every edit is an action.
No additional dependency, and when undo arrives later it is a history over
those actions rather than a rewrite.

Server state is TanStack Query's: `/families` and `/personas` are fetches that
change almost never and are fetched once; `/validate`, `/export` and `/import`
are mutations.

## Layout and interaction

Form on the left, preview on the right, nothing between them. Tabs inside the
form — and **the module list outside the tabs**.

That last point is the one worth repeating, because it is the most direct route
to a broken template: the front, the back and the overview row all reference
the *same* modules. A module list inside a tab would suggest a module belongs
to a view. It belongs to none of them.

**Validation happens on demand**: a button, and a findings panel beneath it.
The export validates anyway — the server refuses an error-carrying draft with
422 and a findings list, which the same panel renders. So nobody exports
without having seen the findings.

This is a deliberate choice over validating on every keystroke. The defect that
issue #4 closed was `/validate` *reporting clean* for invalid drafts — it lied.
It no longer does. Not calling it continuously is a different thing from
calling it and being misled, and an explicit button gives a calmer interface
and one clear moment of truth.

## Preview

The card in CSS. For the skeleton deliberately rough: proportions and wrapping
have to be right, pixels do not.

The persona switcher resolves `${…}` against the selected person, so a layout
is judged against plausible data rather than against placeholder syntax. The
personas gain `sv_SE` and `pt_PT`, which were missing although partners sit in
Lund and Porto; `tr_TR` and `zh_CN` stay, because they are what tests name
lengths and non-Latin scripts.

A code is drawn only when one is chosen, and then for real, with
`@bwip-js/browser`. **NFC without a visible code is the normal case** — then
the area is absent entirely, which moves the layout and therefore has to be
visible.

## Types

Two owners, kept apart, nothing retyped by hand:

* The `Draft` and the routes are generated from the backend's OpenAPI document.
* Google's structures come from `@googleapis/walletobjects`.

## Import and export

Import takes the class and object documents together through a file picker.

Export offers **three individual links**, not a ZIP. Browsers block several
simultaneous downloads, a ZIP costs a dependency, and the manager takes the
files separately anyway.

## Testing

Vitest with React Testing Library. What gets tested is what can fail:

* the reducer, one test per action;
* the API client against a pinned copy of the OpenAPI document;
* one pass through import → edit → export.

**The preview is not unit-tested.** A test that counts CSS classes verifies
nothing a person would judge, and this project has already shipped one test
that could not fail — a coherence check asserting `display_name.startswith(given_name)`
against a `display_name` built by concatenating those two values.

## Sequencing

1. **`Accept-Language` in the backend.** The editor cannot translate findings
   for itself. Building a multilingual interface against a monolingual server
   would surface at the first screenshot.
2. The shell: Vite, generated types, API client, FastAPI serving the build.
3. The front tab and the module list.
4. The preview and the persona switcher.
5. Import and export.

## Risks and open points

* **The back and overview views have no public reference.** Two screenshots,
  one device, dark mode. The card front can be checked against Google's own
  builder; the other two cannot. Mitigated by more screenshots, which have been
  offered and which the later rounds should collect before the fidelity work
  rather than during it.
* **Node in the Dockerfile.** The Python service gains a second toolchain. A
  multi-stage build keeps the final image small, but builds get longer and the
  CI matrix wider.
* **Generated types drift.** If the backend schema changes and nobody
  regenerates, the frontend compiles against a contract that no longer exists.
  A CI step that regenerates and fails on a diff makes green mean the two sides
  agree.
* **The shared `translations` submodule** carries the same rule the dev setup
  states: a submodule pointer must never reference an unpublished commit, and
  the submodule sits on the tip of its branch.
* **The 22 shared domain terms may not cover a library card.** *Balance*,
  *Date of Birth*, *Employee ID* and *Faculty* are there; *Library number* and
  *User group*, both of which appear on a real LMU library pass, are not.
  Missing terms are a contribution to the shared repository, not an obstacle.
