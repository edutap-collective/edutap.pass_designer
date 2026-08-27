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
    list_view: {}, // both ListView fields are optional
    text_modules: [],
    image_modules: [],
    link_modules: [],
    // RedemptionSettings.redemption_issuers and .smart_tap_enabled are
    // required by the generated type (openapi-typescript derives optionality
    // from the OpenAPI `required` array, not from the Pydantic defaults), so
    // an empty object here would not type-check.
    redemption: { redemption_issuers: [], smart_tap_enabled: false },
    unmapped: {},
    // barcode_section is the one optional key on Draft — omit it entirely.
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
