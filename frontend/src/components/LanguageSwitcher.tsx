import { useTranslation } from "react-i18next";
import { SUPPORTED } from "../i18n";

export function LanguageSwitcher() {
  const { i18n } = useTranslation();

  return (
    <select
      value={i18n.resolvedLanguage}
      onChange={(event) => void i18n.changeLanguage(event.target.value)}
      aria-label="Language"
    >
      {SUPPORTED.map((code) => (
        <option key={code} value={code}>
          {code.toUpperCase()}
        </option>
      ))}
    </select>
  );
}
