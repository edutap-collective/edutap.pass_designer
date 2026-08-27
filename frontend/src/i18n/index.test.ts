import { describe, expect, it } from "vitest";
import i18n from "./index";

// The only behaviour this layout round changes, and therefore the only thing
// in it worth a test. The rest is spacing and typography: a test that counted
// CSS classes would verify nothing a person judges, and this project has
// already shipped one test that could not fail.
describe("the document language", () => {
  it("follows the interface language in both directions", async () => {
    await i18n.changeLanguage("de");
    expect(document.documentElement.lang).toBe("de");

    await i18n.changeLanguage("en");
    expect(document.documentElement.lang).toBe("en");
  });
});
