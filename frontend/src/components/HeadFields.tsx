import { useTranslation } from "react-i18next";
import type { HeadField } from "../api/types";
import { useDraft, useDraftDispatch } from "../draft/context";

export function HeadFields({ fields }: { fields: HeadField[] }) {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();

  return (
    <fieldset className="panel">
      <legend className="panel__legend">{t("head.legend")}</legend>
      <div className="field-grid">
        {fields
          .filter((field) => field.scope === "class" || field.scope === "object")
          .map((field) => (
            <label
              key={field.key}
              // An image URI is copied into the exported JSON verbatim, so it
              // is set in the literal face; `text` and `localized_text` are
              // prose a person writes and reads, and stay proportional.
              className={
                field.kind === "image_uri" ? "field field--literal" : "field"
              }
            >
              {/* Deliberately NOT translated. These are the field names of
                  Google's Wallet API — `issuerName`, `programLogo`,
                  `heroImage`. Translating them would cut the one thread a
                  person follows from this form to Google's reference
                  documentation, where they are looked up. The interface
                  chrome around them is translated; these are not chrome. */}
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
      </div>
    </fieldset>
  );
}
