import { describe, expect, it } from "vitest";
import i18n, { currentLanguage } from "./index";

describe("interface translations", () => {
  it("starts in a supported language", () => {
    expect(["en", "de"]).toContain(currentLanguage());
  });

  it("translates a key in both languages", async () => {
    await i18n.changeLanguage("en");
    const english = i18n.t("actions.check");

    await i18n.changeLanguage("de");
    const german = i18n.t("actions.check");

    expect(english).not.toBe("actions.check");
    expect(german).not.toBe("actions.check");
    expect(english).not.toBe(german);
  });

  it("every key in English exists in German", async () => {
    // A missing key renders as the key itself, which looks like a bug to a
    // user and like nothing at all to a test that only checks one key.
    const en = (await import("./en.json")).default;
    const de = (await import("./de.json")).default;

    const flatten = (o: object, p = ""): string[] =>
      Object.entries(o).flatMap(([k, v]) =>
        typeof v === "object" && v !== null
          ? flatten(v, `${p}${k}.`)
          : [`${p}${k}`],
      );

    expect(flatten(de).sort()).toEqual(flatten(en).sort());
  });
});
