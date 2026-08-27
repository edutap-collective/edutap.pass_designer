import { useTranslation } from "react-i18next";
import type { CatalogueField } from "../api/types";
import { useDraft, useDraftDispatch } from "../draft/context";

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
