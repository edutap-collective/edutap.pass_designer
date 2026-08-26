# Pass Designer — Design

**Date:** 2026-08-26
**Status:** agreed, not yet implemented

A snapshot of the design as it stands on the date above. It is not rewritten
when the design changes; a changed decision gets a new document.

## What this is

A stateless web tool for laying out a Google Wallet pass and exporting what
`edutap.pass_builder_manager` needs to turn that layout into a template
version:

* `class_json` — the template: which value appears where, on each of the three
  views a pass has.
* `object_json` — a specimen pass whose runtime-filled values are written as
  `${dotted.field}` placeholders.
* `mappings.json` — the binding table, in the shape of `MappingRulesRequest`
  from `edutap.pass_builder`.

## What this is not

**Not an authoritative source.** The manager owns templates, versions and
publishing. The designer authors three files and hands them over; nothing it
produces is binding until a person loads it into the manager.

**Not a client of the Google Wallet API.** It creates nothing at Google, reads
nothing from Google, and holds no Google credentials.

**Not a store.** No database, no accounts, no saved drafts. A design enters as
files and leaves as files. Version history is Git's job, in whichever
repository the exported files come to rest.

**Not a faithful renderer.** The preview is close enough to make layout
decisions on — proportions, wrapping, whether a row fits. It is not a
pixel-accurate reproduction of the Wallet app, and it should not pretend to be.

## Where it sits

```
                     ┌─────────────────────────┐
                     │  edutap.pass_designer   │  ← this
                     │  (stateless, no auth)   │
                     └───────────┬─────────────┘
                     three files │ carried by a person
                                 ▼
                     ┌─────────────────────────┐
                     │ pass_builder_manager    │  templates, versions,
                     │ (planned)               │  credentials, publishing
                     └───────────┬─────────────┘
                                 │ edutap.pass_builder_api
                                 ▼
                     ┌─────────────────────────┐
                     │ edutap.pass_builder     │  renders a pass from a
                     │                         │  template plus person data
                     └─────────────────────────┘
```

Dependencies the designer actually takes:

* `edutap.wallet-google` — the Pydantic models for all seven pass families.
  Models only; the API client is not used.
* `@googleapis/walletobjects` (Apache-2.0) — the TypeScript types for the same
  structures, in the browser.
* `Faker` (MIT) — preview personas.
* `@bwip-js/browser` (MIT) — barcode rendering.

Neighbouring work this design has filed, and which it does not wait for:

* [`edutap.pass_builder_manager#1`](https://github.com/edutap-collective/edutap.pass_builder_manager/issues/1)
  — export the field catalogue as a static document.
* [`edutap.image_service#15`](https://github.com/edutap-collective/edutap.image_service/issues/15)
  — separate endpoints and delivery path for static institutional images.
* [`edutap.wallet_google#101`](https://github.com/edutap-eu/edutap.wallet_google/issues/101)
  — expose Google's required-field set as queryable metadata.
* [`edutap.wallet_google#102`](https://github.com/edutap-eu/edutap.wallet_google/issues/102)
  — ship the `${…}` placeholder resolver there.

## The three views

A Google Wallet pass is seen in three places, and `ClassTemplateInfo` carries a
separate override for each. They are not variations of one layout; they have
different shapes.

### Front — `cardTemplateOverride`, plus `cardBarcodeSectionDetails`

A **grid**. An ordered list of rows; each row holds one, two or three cells
(`oneItem` / `twoItems` / `threeItems`). Each cell is a `TemplateItem`.

`cardBarcodeSectionDetails` adds text above and below the code area. It belongs
to this view rather than being a view of its own.

### Back — `detailsTemplateOverride`

A **flat list**, not a grid. `DetailsItemInfo` holds exactly one
`item: TemplateItem`; there is no one/two/three choice. Observed in the Wallet
app: label above value, stacked vertically, one pair per row. Long values get a
disclosure chevron from Google — truncation is not the designer's job, but
showing that it will happen is.

`linksModuleData` renders here as its own block with globe icons, and is
prominent enough to deserve its own section in the editor rather than being
carried along as unmapped data.

### List — `listTemplateOverride`

**Two rows**, not three. `firstRowOption` (a `FirstRowOption`, either a transit
option or a field selector) and `secondRowOption` (a `FieldSelector`).
`thirdRowOption` is deprecated and already carries `exclude=True` in
`edutap.wallet-google`: *"Setting it will have no effect on what the user
sees."*

This view is why the tab exists. A real LMU library pass takes four wrapped
lines in the Wallet overview where a comparable pass takes two, because a long
institution name sits in the row options. That is invisible in the JSON and
invisible in Google's own pass builder; it shows up only when someone opens
their Wallet. The preview must wrap exactly as the app does rather than
truncating, or it hides the one defect it exists to reveal.

### Where the designer's influence ends

Below the pass ID, the back view is Google's own chrome: alias, the Smart Tap
toggle, notification settings, sharing notes, archive and remove, and a legal
footer. None of it is designable. The preview renders it dimmed and labelled,
so that nobody searches for the setting that would change it.

## Interaction model

A form on one side, a live preview on the other, with the preview following
every keystroke. Selecting a field in the form highlights the corresponding
element in the preview, and vice versa.

Three tabs in the form, one per view. **The module list sits outside the tabs**,
because `textModulesData`, `imageModulesData` and `linksModuleData` are shared
by all three views: front, back and list all reference the same modules by
`fieldPath`. Putting the list inside a tab would suggest a module belongs to a
view. It belongs to none of them, and misunderstanding that is the most direct
route to a broken template.

## Domain model

Google's structure is too deeply nested to edit directly —
`cardRowTemplateInfos[] → twoItems → startItem → firstValue → fields[] →
fieldPath` is six levels for "the name goes on the left". The editor works on a
flat intermediate model and translates only at the edges.

```python
class FieldRef(BaseModel):
    """One reference in a fallback chain."""

    kind: Literal["text", "image"]
    module_id: str                     # -> object.textModulesData['<id>']
    date_format: DateFormat | None = None


class Line(BaseModel):
    """A displayed value. The first non-empty reference wins."""

    fallback_chain: list[FieldRef]     # -> FieldSelector.fields


class Cell(BaseModel):
    """One column of a front row, or one entry of the back list."""

    first: Line | None = None
    second: Line | None = None         # only valid when `first` is set


class Row(BaseModel):
    cells: list[Cell]                  # 1..3 -> oneItem / twoItems / threeItems


class ListView(BaseModel):
    """`thirdRowOption` is deprecated upstream and is not modelled."""

    # `firstRowOption` is either a field reference or, for Transit only, a
    # `transitOption`. The union is not collapsed, because collapsing it would
    # make the Transit case unreachable from the editor.
    first_row: Line | TransitOption | None = None
    second_row: Line | None = None


class Draft(BaseModel):
    family: FamilyId
    head: dict[str, LocalizedText]     # keys declared by the family descriptor
    front_rows: list[Row]
    barcode_section: BarcodeSection | None = None
    back_items: list[Cell]             # flat, one TemplateItem each
    list_view: ListView
    text_modules: list[TextModuleDraft]
    image_modules: list[ImageModuleDraft]
    link_modules: list[LinkModuleDraft]
    redemption: RedemptionSettings
    unmapped: dict[str, Any] = {}
```

Two properties of this model matter more than its shape.

**The fallback chain is a first-class concept.** `FieldSelector.fields` is not
a list of things to show; it is a list of things to try. Google: *"If more than
one reference is supplied, then the first one that references a non-empty field
will be displayed."* That is how one template serves both students and staff —
`[id, matriculation_number]` shows whichever the person has. The editor calls
it a fallback chain, shows it as an ordered list, and never presents it as
"several values in a cell".

`firstValue` and `secondValue` are a different thing again: they render as one
element with a slash between them, and `secondValue` may only be set when
`firstValue` is. The editor enforces the dependency rather than letting the
export fail.

**`unmapped` carries everything the designer does not understand.** On import,
`securityAnimation`, `callbackOptions`, `messages`, `notifications`,
`passConstraints` and anything else unrecognised is kept verbatim and written
back unchanged on export. A tool that silently drops fields when opening and
saving is used exactly once.

## Families

All seven pass families registered in `edutap.wallet-google`: Generic,
GiftCard, Loyalty, Offer, EventTicket, Transit, Flight. (`Issuer`,
`Permissions`, `SmartTap`, `Reference` and `JwtResource` are registered there
too but are not pass types.)

A family is a **descriptor written as Python code in the backend** and served to
the frontend over an endpoint. It declares:

* which head fields exist, their labels and their kinds;
* which fields Google requires on creation;
* which Pydantic class and object model to build;
* which preview template renders it.

The frontend builds its form from the descriptor. There is no per-family form
code and no per-family TypeScript, because a second declaration in the browser
would drift from the one the export validates against — and the drift only
shows up when the export rejects something the form offered.

**The required-field set cannot be derived from the models.** Measured:
`GenericObject` requires only `id` and `classId` in Pydantic, while Google's
reference also demands `cardTitle` and `header`; `LoyaltyClass` requires only
`id`, while Google also demands `issuerName`, `programName` and `reviewStatus`.
The descriptors carry this knowledge, written out per family from the REST
reference. `edutap.wallet_google#101` asks for it upstream; until it lands, the
descriptors are its home.

Flight and Transit are the expensive two: `FlightClass` needs `flightHeader`,
`origin` and `destination` as structures, not as text fields.

## Values: constant or bound

Every text module carries one value and a statement about what it is:

```python
class TextModuleDraft(BaseModel):
    module_id: str                     # -> textModulesData[].id
    header: LocalizedText
    value: str                         # constant text, or "${dotted.field}"
    bound: bool                        # False -> the value is fixed
```

A constant is written through unchanged — "Ludwig-Maximilians-Universität
München" is the same on every pass. A bound value is written as
`${dotted.field}` and filled at issuing time.

The syntax is the manager's, deliberately: `${dotted.field}`, `$$` for a
literal dollar sign, substitution in string values only, never in keys. A
syntax the manager cannot read would be worse than none. The export refuses a
lone `$` that is neither `$$` nor the start of a `${…}` — that is the mistake
that otherwise slips through and surfaces as a literal dollar sign on somebody's
card.

There is no separate sample value. The preview resolves placeholders against a
persona, which is the same path the manager takes at runtime with real data.
Keeping a specimen value beside the placeholder would mean the preview showed
something the pass never would.

## Preview personas

Generated locally with Faker; no real person's data is needed to lay out a
pass, and none is permitted.

A persona is drawn **as a whole**: locale and gender are chosen once and
everything else is derived from them, so that the person has a coherent name,
birth date and affiliation instead of a name from one country and a birthplace
from another. The seed is fixed, so a layout comparison between two states is
not confounded by a changing name.

The set on offer:

* one female, one male and one non-binary persona (`name_female`, `name_male`,
  `name_nonbinary` — all three verified present in Faker across `de_DE`,
  `en_US`, `fr_FR`, `tr_TR`, `zh_CN`);
* several locales, so that long names, non-Latin scripts and diacritics are
  visible against the layout rather than discovered in production;
* one deliberately sparse persona with empty fields, which is the only way to
  see a fallback chain actually do something.

The persona switcher is the real inspection tool: a layout that survives all of
them is a layout that will survive a population.

Mapping a catalogue field to a Faker provider is an explicit table in the
designer, next to the catalogue, falling back to `value_type`. An unmapped
field produces something visibly generic (`text-1234`) rather than something
plausible, so a gap in the table is noticed rather than believed.

## Field catalogue

The catalogue lists what a data provider can deliver, so that placeholders come
from a picklist instead of memory and `RuleSpec.value_type` is right by
construction. Its shape is `CatalogueField` as it already exists in
`edutap.pass_builder`: `key`, `value_type`, `label`, `required`, `description`.

The designer holds no credential, so it does not fetch the catalogue. It reads
a `catalogue.json` file.

**The repository ships a neutral example catalogue, not an institution's.**
This resolves a conflict between two otherwise settled decisions: the catalogue
was to be checked in and versioned, *and* a university's person-data field
structure was judged not to belong in public. The repository is public, so the
checked-in file carries eduTAP-generic field keys only. A real catalogue is
loaded through the same override path a newer one would use — dropped into the
running tool — and never committed here.

The versioned-diff benefit is kept for the example, which is what documents the
expected shape.

## Images

Google fetches every image itself from a publicly reachable `sourceUri`, so a
URL is the only thing that can be exported. The editor takes URLs for logo,
wide logo, hero image and the images referenced from rows.

A local file may be dropped in as well, but it feeds **the preview only** and is
labelled as not exported — so that a layout can be judged against a real
photograph without publishing it first. The export writes the placeholder at
that position, never a data URI.

Hosting is out of scope here and belongs to `edutap.image_service`, which
stores and serves person photographs under a stable URL today and has been
asked for a separate static-asset path (`#15`).

## Codes and Smart Tap

NFC without a visible code is the normal case, and `barcode` is optional on the
object — so a pass with no code emits no `barcode` key at all. This is the
capability Google's own pass builder cannot express: its `buildGenericObject`
writes a `barcode` block unconditionally, and the word `smartTap` does not
appear anywhere in its source.

Smart Tap is set as the API requires: `enableSmartTap` and `redemptionIssuers`
on the class, `smartTapRedemptionValue` on the object (ASCII only).

Where a code *is* wanted, it is rendered for real with `@bwip-js/browser`,
which covers all eleven drawing symbologies Google offers — Aztec, PDF417,
Code 39, Code 128, Codabar, DataMatrix, EAN-8, EAN-13, ITF-14, QR, UPC-A.
(`TEXT_ONLY` draws nothing by definition.) A placeholder image would be a
falsehood at exactly the spot a designer is looking at, and it would misstate
the footprint, which is what actually moves the layout.

## Import

Class and object JSON together. The class alone is not editable, because its
`fieldPath` references would point at nothing.

Recognised `${…}` placeholders become bound values again. Everything
unrecognised goes to `unmapped` and returns unchanged on export.

## Export

Three files, or the same payloads over the manager's API later:

| File | Shape | Manager endpoint (later) |
|---|---|---|
| `class_json` | `GenericClass` &c. | `POST /variants/{id}/versions` |
| `object_json` | `GenericObject` &c. | same request body |
| `mappings.json` | `MappingRulesRequest` | `PUT /versions/{id}/mappings` |

Nothing new is invented: the mapping file is `{"rules": [RuleSpec, …]}` exactly
as `edutap.pass_builder` already defines it. One format, two delivery paths.

Issuer IDs and class suffixes are ordinary head fields with a recognisable
default. The designer creates nothing at Google and guesses no identifiers.

## Validation

Three layers, in the order they catch things:

1. **In the form.** Volume limits are enforced where the entry is made, not
   reported at the end: a warning from the sixth entry, and the control is
   disabled at ten (`textModulesData` allows at most ten per level,
   `linksModuleData` at most ten combined). A warning at export time would mean
   someone finishes a layout and only then learns that three of its rows will
   never appear.

2. **Cross-checks the models cannot make.** Every `fieldPath` must resolve to a
   module that exists in the object. Google discards unknown references
   **silently** — the row simply does not appear, with no error anywhere. This
   is the single most important check in the tool, because the failure is
   invisible on both sides.

3. **The Pydantic models, server-side, before export.** `edutap.wallet-google`
   is the last word: enums, types, structure. The browser-side schemas are for
   comfort, not for authority.

## Architecture

FastAPI behind, React in front. Stateless throughout.

| Module | Responsibility | Does not know |
|---|---|---|
| `platforms/google/families/` | descriptors: head fields, required set, models, templates | the row grid |
| `draft/` | the intermediate model | Google JSON |
| `exporter/` | `Draft` → class, object, rules | HTTP |
| `importer/` | class + object → `Draft` | HTTP |
| `personas/` | Faker personas and the field mapping table | layout |
| `web/` | routers, the descriptor endpoint | what a pass looks like |

`exporter`, `importer` and the preview are reached through protocols rather
than direct calls, so a second platform attaches as an implementation rather
than as a change to the grid. That is the only concession to Apple and Samsung:
a seam, no code. A platform-neutral model written without a single non-Google
implementation would be neutral in the wrong places.

### Frontend

React, Vite, TanStack Query.

The choice is driven by one property: the preview is derived state that changes
on every keystroke, and the server holds no state at all. Server-rendered
fragments would mean a round trip per keystroke to re-render something the
server does not own, and the two-way highlighting between form and preview is
client-side work in any case.

Types come from two owners, kept apart:

* Google's structures belong to Google and change with Google →
  `@googleapis/walletobjects`.
* The `Draft` model belongs to us and changes with the interface → defined once
  in Pydantic, TypeScript generated from the OpenAPI schema.

`@googleapis/walletobjects` ships types only — every field optional, every field
nullable — so it catches typos and not omissions. A thin in-repo module wraps
it with runtime schemas and the required-field knowledge from the descriptors.
It lives in its own directory with its own tests from the start, so that
extracting it into a package later is a move rather than an operation. It is
not a package now, because there is exactly one consumer.

## Operations

An admin tool, containerised from the start, run locally during development and
deployed under `/portale/pass-designer` on the `portal-mgmt` vhost when someone
outside the team needs it.

Access control is inherited, not built: the cluster sits in its own network
segment behind a separate firewall, the entrypoint is not reachable from the
general campus network, and the regular route runs through the WebFE, which
enforces Shibboleth and MFA. A login of its own would be a second truth beside
Shibboleth.

Two details that have bitten this pattern before: Traefik passes the path
through unchanged, so the router needs `StripPrefix`; and a React SPA under a
path prefix needs Vite's `base` set, or it requests its own assets from the
root and serves a white page. Both read the prefix from one variable, so they
cannot drift apart.

## Order of work

The grid, import, export, preview, personas and validation are
family-independent and are built once. Only the descriptors are staged:

1. **Loyalty** — the library card, and the first proof that generic form
   generation from a descriptor actually works.
2. **Generic** — the student and staff ID.
3. **EventTicket**.
4. **GiftCard, Offer, Transit, Flight**.

All seven are declared through the same mechanism from the beginning. None is a
special case sitting beside it.

## Deferred, deliberately

* **Apple and Samsung.** Apple template versions are `.pkpasstemplate` bundles
  with assets, structurally unlike a JSON pair; `edutap.wallet_samsung` has no
  source at all yet. The seam is placed, no code is written against it.
* **Writing to the manager.** It needs a credential, and the designer holds
  none. The path stays as designed — three files, carried by a person. Low
  priority; the interface comes first.
* **Image hosting** via `edutap.image_service`.
* **The barcode section** is in scope, but rotating barcodes are not.

## Risks and open points

* **The preview's fidelity is unverified beyond two screenshots.** The card
  view can be checked against Google's own builder; the back and list views
  have no public reference, and the two screenshots on hand are one pass on one
  device in dark mode. Light mode, longer values and other Android versions are
  unmeasured. Anything derived from them describes what the app did on the day
  it was looked at.
* **The required-field tables are hand-copied from the REST reference** for
  seven families, and Google changes that reference without notice. Until
  `wallet_google#101` lands, drift is caught only by the API rejecting an
  export.
* **`pass_builder_manager` does not exist yet.** Nothing here waits for it, but
  the hand-off is a hand-off to a plan rather than to a service.
* **Faker's coverage of non-binary names varies by locale.** Verified present
  in five; the rest are unchecked, and a missing provider must degrade visibly
  rather than silently falling back to a gendered name.
