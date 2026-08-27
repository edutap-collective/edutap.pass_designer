# edutap.pass_designer

Lays out a Google Wallet pass and hands the result to
[`edutap.pass_builder_manager`](https://github.com/edutap-collective/edutap.pass_builder_manager).

A pass is seen in three places — the card, the detail view behind it, and the
row in the Wallet overview — and each has its own template. The designer edits
all three side by side with a live preview, and exports what the manager needs
to make a template version out of them:

* `class_json` — the layout.
* `object_json` — a specimen pass, with runtime values written as
  `${dotted.field}`.
* `mappings.json` — the binding table, in the shape `edutap.pass_builder`
  already defines.

**Status: a walking skeleton.** The FastAPI backend is complete — draft
model, exporter, importer, six HTTP routes — and a React editor now sits in
front of it, served from `/`. The editor can lay out the card front (head
fields, rows, shared text modules), preview it against a generated persona,
run Check and see findings translated into English or German, and Export or
Import the three artefacts. It cannot yet edit the back or the Wallet
overview row, edit image modules, or offer a real `classId`/`objectId` — see
the limitation below. The agreed design is
[`docs/superpowers/specs/2026-08-27-pass-designer-editor-design.md`](docs/superpowers/specs/2026-08-27-pass-designer-editor-design.md),
building on the backend design in
[`docs/superpowers/specs/2026-08-26-pass-designer-design.md`](docs/superpowers/specs/2026-08-26-pass-designer-design.md).

**Known limitation: the exported `classId`/`objectId` are placeholders.**
Export writes `ISSUER.class` and `ISSUER.specimen` verbatim into the
downloaded `class.json` and `object.json` — there is no UI for them yet.
Edit them before handing the files to the pass builder manager, or they will
collide with every other export made from this tool.

## Running it

See [`docs/how-to/run-the-service.md`](docs/how-to/run-the-service.md) for
running the service in a container or directly with `uvicorn`, and for the
routes it exposes.

For the backend: `make test-local` runs the test suite, and `make lint` runs
`ruff` and `ty`.

For the editor, in [`frontend/`](frontend/): a **pnpm**-managed React app on
the Node version pinned in [`.nvmrc`](.nvmrc). `make test-frontend` runs its
tests (`pnpm vitest run`) and `make build-frontend` builds it
(`pnpm build`) into the static files the backend serves from `/` — see
["Behind a path prefix"](docs/how-to/run-the-service.md#behind-a-path-prefix)
for why the deployment prefix has to be set at build time, not just at run
time.

## What it is deliberately not

**Not an authoritative source.** It authors three files; the manager owns
templates, versions and publishing. Nothing produced here is binding until a
person loads it.

**Not a client of the Google Wallet API.** It creates nothing at Google and
holds no Google credentials.

**Not a store.** No database, no accounts, no saved drafts — a design enters as
files and leaves as files.

## Why it exists rather than Google's pass builder

Google publishes a pass builder of its own, and it cannot express the passes we
issue. Its object builder writes a `barcode` block unconditionally, so a pass
carrying only NFC is not representable; the word `smartTap` does not appear in
its source at all; and its class builder emits single-field rows only, with no
way to place an image in a row — which is how a photo gets onto an identity
card.

It also stops at the card. The detail view and the overview row, where most of
a library card's information actually lives, have no editor anywhere.

## Preview data

Preview personas are generated with Faker: female, male and non-binary, across
several locales, plus one deliberately sparse persona that shows what a
fallback chain does when a field is empty. No real person's data is needed to
lay out a pass, and none belongs here.

The field catalogue checked into this repository is a neutral example. A real
one is loaded into the running tool and is not committed.
