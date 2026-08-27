import { useTranslation } from "react-i18next";
import type { CatalogueField, TextModuleDraft } from "../api/types";
import { useDraft, useDraftDispatch } from "../draft/context";

/**
 * Return an id that cannot collide with any text module already on the draft.
 *
 * `module_${length + 1}` is not safe: an imported artefact can carry a gap in
 * its own numbering (any foreign class can, and Import exists to take
 * foreign artefacts) — one module id `module_2` and nothing else — and the
 * next "Add module" click would then land on `module_2` again, silently
 * merging two unrelated modules into one.
 *
 * Chosen over `crypto.randomUUID()` for readability: these ids appear
 * verbatim in the exported `fieldPath` and in `mappings.json`, where a
 * person debugging a template benefits from `module_3` over an opaque UUID.
 * The backend validator (`check_duplicate_module_ids`) is the layer that
 * must not let a collision out regardless of what the editor generates, so
 * this only has to be good enough to not manufacture one on the happy path.
 */
export function nextTextModuleId(modules: TextModuleDraft[]): string {
  const highest = modules.reduce((max, module) => {
    const match = /^module_(\d+)$/.exec(module.module_id);
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0);
  return `module_${highest + 1}`;
}

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
            moduleId: nextTextModuleId(draft.text_modules),
          })
        }
      >
        {t("actions.addModule")}
      </button>
    </fieldset>
  );
}
