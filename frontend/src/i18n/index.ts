import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import de from "./de.json";
import en from "./en.json";

// French, Portuguese and Swedish follow. Adding one is a catalogue and an
// entry here — no component changes, because no component holds a string.
export const SUPPORTED = ["en", "de"] as const;

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, de: { translation: de } },
    supportedLngs: [...SUPPORTED],
    fallbackLng: "en",
    interpolation: { escapeValue: false },
  });

export function currentLanguage(): string {
  return i18n.resolvedLanguage ?? "en";
}

/**
 * Keep `<html lang>` on the language the interface is actually showing.
 *
 * The document ships with a hard-coded `lang="en"`. Screen readers pick their
 * pronunciation from that attribute, so a German interface left at "en" is
 * read aloud by an English voice — which is not a cosmetic problem for
 * someone who depends on it. Nothing else in the app touches the attribute,
 * so the language switcher has to.
 */
function syncDocumentLanguage(language: string): void {
  document.documentElement.lang = language;
}

i18n.on("languageChanged", syncDocumentLanguage);
syncDocumentLanguage(currentLanguage());

export default i18n;
