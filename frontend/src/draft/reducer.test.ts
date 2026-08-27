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
