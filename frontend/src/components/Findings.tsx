import { useTranslation } from "react-i18next";
import type { Finding } from "../api/types";

// `null` means "not checked yet", which is a different thing from "checked and
// clean". Conflating them would let an unchecked draft look approved.
export function Findings({ findings }: { findings: Finding[] | null }) {
  const { t } = useTranslation();

  if (findings === null) return <p>{t("findings.notCheckedYet")}</p>;
  if (findings.length === 0) return <p>{t("findings.none")}</p>;

  const ordered = [
    ...findings.filter((f) => f.severity === "error"),
    ...findings.filter((f) => f.severity !== "error"),
  ];

  return (
    <ul aria-label={t("findings.error")}>
      {ordered.map((finding, index) => (
        <li key={index} data-severity={finding.severity}>
          <strong>
            {finding.severity === "error"
              ? t("findings.error")
              : t("findings.warning")}
          </strong>{" "}
          <code>{finding.location}</code> — {finding.message}
        </li>
      ))}
    </ul>
  );
}
