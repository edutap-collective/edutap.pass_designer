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
  const [refused, setRefused] = useState(false);
  const [classFile, setClassFile] = useState<File | null>(null);
  const [objectFile, setObjectFile] = useState<File | null>(null);

  async function onCheck() {
    setRefused(false);
    setFindings(await checkDraft(draft));
  }

  async function onExport() {
    setRefused(false);
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
      setRefused(true);
    }
  }

  async function onImport() {
    if (!classFile || !objectFile) return;
    dispatch({
      type: "replaceDraft",
      draft: await importFiles(draft.family, classFile, objectFile),
    });
    setFindings(null);
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

      {refused ? <p role="alert">{t("export.refused")}</p> : null}
      <Findings findings={findings} />
    </section>
  );
}
