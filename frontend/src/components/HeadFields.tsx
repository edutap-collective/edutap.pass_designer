import { useTranslation } from "react-i18next";
import type { HeadField } from "../api/types";
import { useDraft, useDraftDispatch } from "../draft/context";

export function HeadFields({ fields }: { fields: HeadField[] }) {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();

  return (
    <fieldset>
      <legend>{t("head.legend")}</legend>
      {fields
        .filter((field) => field.scope === "class" || field.scope === "object")
        .map((field) => (
          <label key={field.key}>
            {field.label}
            {field.required ? " *" : ""}
            <input
              type={field.kind === "colour" ? "color" : "text"}
              value={draft.head[field.key] ?? ""}
              onChange={(e) =>
                dispatch({ type: "setHead", key: field.key, value: e.target.value })
              }
            />
          </label>
        ))}
    </fieldset>
  );
}
