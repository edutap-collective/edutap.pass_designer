import { describe, expect, it } from "vitest";
import { resolvePlaceholders } from "./resolve";

const values = { "person.display_name": "Isolde Reichmann" };

describe("resolvePlaceholders", () => {
  it("substitutes a known field", () => {
    expect(resolvePlaceholders("${person.display_name}", values)).toBe(
      "Isolde Reichmann",
    );
  });

  it("substitutes inside surrounding text", () => {
    expect(resolvePlaceholders("Hello ${person.display_name}!", values)).toBe(
      "Hello Isolde Reichmann!",
    );
  });

  it("turns a doubled dollar into a literal one", () => {
    expect(resolvePlaceholders("costs 5$$", values)).toBe("costs 5$");
  });

  it("leaves an unknown field visible rather than blank", () => {
    // Blanking it would make a missing binding look like an empty field. The
    // designer has to see that nothing filled it.
    expect(resolvePlaceholders("${person.nonesuch}", values)).toBe(
      "${person.nonesuch}",
    );
  });
});
