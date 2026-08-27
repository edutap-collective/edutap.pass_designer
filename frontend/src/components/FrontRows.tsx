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
            aria-label={t("rows.row", { number: rowIndex + 1 })}
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
              aria-label={t("rows.cell", { row: rowIndex + 1, cell: cellIndex + 1 })}
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

          <button
            type="button"
            aria-label={t("rows.remove", { number: rowIndex + 1 })}
            onClick={() => dispatch({ type: "removeRow", row: rowIndex })}
          >
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
