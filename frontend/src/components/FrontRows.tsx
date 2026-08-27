import { useTranslation } from "react-i18next";
import { useDraft, useDraftDispatch } from "../draft/context";

export function FrontRows() {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();

  return (
    <fieldset className="panel">
      <legend className="panel__legend">{t("tabs.front")}</legend>

      {draft.front_rows.map((row, rowIndex) => (
        <div className="row" key={rowIndex}>
          {/* Without this the row is a line of anonymous dropdowns: the row
              number lives only in the aria-labels below, so a sighted person
              reads nothing at all. Hidden from the accessibility tree because
              the controls already carry that same name. */}
          <span className="row__marker" aria-hidden="true">
            {t("rows.row", { number: rowIndex + 1 })}
          </span>

          <select
            className="row__count"
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
              className="row__cell"
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
            className="row__remove"
            aria-label={t("rows.remove", { number: rowIndex + 1 })}
            onClick={() => dispatch({ type: "removeRow", row: rowIndex })}
          >
            ×
          </button>
        </div>
      ))}

      <button
        type="button"
        className="button button--quiet"
        onClick={() => dispatch({ type: "addRow" })}
      >
        {t("actions.addRow")}
      </button>
    </fieldset>
  );
}
