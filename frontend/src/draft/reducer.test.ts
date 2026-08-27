import { describe, expect, it } from "vitest";
import { draftReducer, emptyDraft, type DraftAction } from "./reducer";
import type { Draft } from "../api/types";

const base = emptyDraft("loyalty");

/**
 * Recursively freezes an object graph so that any mutation attempt under
 * strict mode (which ES modules always run in) throws a TypeError instead
 * of silently succeeding.
 */
function deepFreeze<T>(value: T): T {
  if (value && typeof value === "object") {
    for (const child of Object.values(value as Record<string, unknown>)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

/**
 * A draft with something in every collection the reducer touches, so that
 * freezing it actually proves something — an empty draft has nothing left
 * to mutate.
 */
function populatedDraft(): Draft {
  return {
    ...emptyDraft("loyalty"),
    head: { issuerName: "Example University" },
    front_rows: [
      {
        cells: [
          {
            first: {
              fallback_chain: [{ kind: "text", module_id: "name" }],
            },
          },
        ],
      },
    ],
    text_modules: [{ module_id: "name", value: "Example", bound: false }],
  };
}

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


// Purity is not an implementation detail: it is the reason a reducer was
// chosen over a state library at all. Undo-as-a-history-of-actions only
// holds while no action ever mutates the state it is given. The `setHead`
// test above only proves this for one of nine branches; this sweep proves
// it for all of them, against a draft that actually has something to lose.
describe("draftReducer purity", () => {
  const actions: { name: string; action: DraftAction }[] = [
    { name: "setHead", action: { type: "setHead", key: "issuerName", value: "Other" } },
    { name: "addRow", action: { type: "addRow" } },
    { name: "removeRow", action: { type: "removeRow", row: 0 } },
    { name: "setRowCells", action: { type: "setRowCells", row: 0, cells: 3 } },
    {
      name: "setCellField",
      action: { type: "setCellField", row: 0, cell: 0, kind: "text", moduleId: "other" },
    },
    { name: "addTextModule", action: { type: "addTextModule", moduleId: "other" } },
    { name: "removeTextModule", action: { type: "removeTextModule", moduleId: "name" } },
    {
      name: "setTextModule",
      action: {
        type: "setTextModule",
        moduleId: "name",
        patch: { value: "changed", bound: true },
      },
    },
    {
      name: "replaceDraft",
      action: { type: "replaceDraft", draft: emptyDraft("membership") },
    },
  ];

  it.each(actions)("$name does not mutate the draft it is given", ({ action }) => {
    const pristine = populatedDraft();
    const frozen = deepFreeze(structuredClone(pristine));

    expect(() => draftReducer(frozen, action)).not.toThrow();
    expect(frozen).toEqual(pristine);
  });
});

describe("draftReducer exhaustiveness", () => {
  it("throws on an unknown action instead of silently blanking the draft", () => {
    const bogus = { type: "bogusAction" } as unknown as DraftAction;

    expect(() => draftReducer(base, bogus)).toThrow(/unhandled draft action/);
  });
});
