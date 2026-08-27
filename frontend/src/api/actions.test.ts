import { describe, expect, it, vi, beforeEach } from "vitest";
import { downloadJson } from "./actions";

describe("downloadJson", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("offers one file per artefact, named after it", () => {
    const click = vi.fn();
    vi.spyOn(document, "createElement").mockReturnValue({
      click,
      href: "",
      download: "",
      remove: vi.fn(),
    } as unknown as HTMLAnchorElement);
    vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL: vi.fn() });

    downloadJson("class.json", { id: "1.a" });

    expect(click).toHaveBeenCalledOnce();
  });
});
