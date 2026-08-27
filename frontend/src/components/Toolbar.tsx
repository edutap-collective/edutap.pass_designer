import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Finding } from "../api/types";
import { checkDraft, downloadJson, exportDraft, importFiles } from "../api/actions";
import { useDraft, useDraftDispatch } from "../draft/context";
import { Findings } from "./Findings";

export function Toolbar() {
  const draft = useDraft();
  const dispatch = useDraftDispatch();
  const { t } = useTranslation();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  // Whichever of Export or Import goes wrong, it lands here — one place to
  // look, and one `<p role="alert">` below, rather than a flag per button.
  const [alertKey, setAlertKey] = useState<string | null>(null);
  const [classFile, setClassFile] = useState<File | null>(null);
  const [objectFile, setObjectFile] = useState<File | null>(null);

  async function onCheck() {
    setAlertKey(null);
    try {
      setFindings(await checkDraft(draft));
    } catch {
      // A failed Check must not leave the previous result standing: "no
      // problems found" from a draft that was never actually re-checked
      // reads as an affirmative approval it never earned. `null` is the
      // panel's own "not checked yet" state, and that is the truth here.
      setFindings(null);
      setAlertKey("check.failed");
    }
  }

  async function onExport() {
    setAlertKey(null);
    try {
      const result = await exportDraft(draft, "ISSUER.class", "ISSUER.specimen");
      setFindings([]);
      downloadJson("class.json", result.class_json);
      downloadJson("object.json", result.object_json);
      downloadJson("mappings.json", result.mappings);
    } catch (error) {
      // The 422 carries the findings list. Showing it in the same panel as
      // Check means one place to look, whichever button was pressed.
      const detail = error as { findings?: Finding[] };
      setFindings(detail.findings ?? []);
      setAlertKey("export.refused");
    }
  }

  async function onImport() {
    if (!classFile || !objectFile) return;
    setAlertKey(null);
    try {
      const imported = await importFiles(draft.family, classFile, objectFile);
      dispatch({ type: "replaceDraft", draft: imported });
      setFindings(null);
    } catch {
      // A bad file, an unknown family, a backend error — the draft is never
      // touched (dispatch above is only reached on success), but the person
      // pressing the button still has to be told something happened.
      setAlertKey("import.failed");
    }
  }

  return (
    <section>
      <button type="button" onClick={() => void onCheck()}>
        {t("actions.check")}
      </button>
      <button type="button" onClick={() => void onExport()}>
        {t("actions.export")}
      </button>

      <label>
        {t("export.classJson")}
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setClassFile(e.target.files?.[0] ?? null)}
        />
      </label>
      <label>
        {t("export.objectJson")}
        <input
          type="file"
          accept="application/json"
          onChange={(e) => setObjectFile(e.target.files?.[0] ?? null)}
        />
      </label>
      <button type="button" onClick={() => void onImport()} disabled={!classFile || !objectFile}>
        {t("actions.import")}
      </button>

      {alertKey ? <p role="alert">{t(alertKey)}</p> : null}
      <Findings findings={findings} />
    </section>
  );
}
