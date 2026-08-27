import { describe, expect, it } from "vitest";
import type { Draft, Finding } from "./types";

describe("generated types", () => {
  it("carries the draft's own field names", () => {
    // A compile-time assertion: if the backend renames a field, this stops
    // building. That is the point — the alternative is a runtime surprise.
    const draft: Draft = {
      family: "loyalty",
      head: {},
      front_rows: [],
      back_items: [],
      list_view: {},
      text_modules: [],
      image_modules: [],
      link_modules: [],
      redemption: { redemption_issuers: [], smart_tap_enabled: false },
      unmapped: {},
    };

    expect(draft.family).toBe("loyalty");
  });

  it("carries the finding shape the panel renders", () => {
    const finding: Finding = {
      severity: "error",
      message: "something",
      location: "head",
    };

    expect(finding.severity).toBe("error");
  });
});
