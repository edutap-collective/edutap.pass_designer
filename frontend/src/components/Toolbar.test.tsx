import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Toolbar } from "./Toolbar";
import "../i18n";

// The draft and its dispatch are mocked rather than provided by a real
// DraftProvider, so a failed import can be proven to leave the draft
// unchanged by asserting `dispatch` — the only way to change it — was never
// called, rather than inferring "unchanged" from an untouched default.
const dispatch = vi.fn();
vi.mock("../draft/context", () => ({
  useDraft: () => ({ family: "loyalty", head: {}, front_rows: [] }),
  useDraftDispatch: () => dispatch,
}));

const importFiles = vi.fn();
const checkDraft = vi.fn();
vi.mock("../api/actions", () => ({
  checkDraft: (...args: unknown[]) => checkDraft(...args),
  exportDraft: vi.fn(),
  downloadJson: vi.fn(),
  importFiles: (...args: unknown[]) => importFiles(...args),
}));

function jsonFile(name: string): File {
  return new File(["{}"], name, { type: "application/json" });
}

describe("Toolbar import", () => {
  it("shows a message and leaves the draft unchanged when the import fails", async () => {
    importFiles.mockRejectedValue(new Error("bad artefact"));
    const user = userEvent.setup();
    render(<Toolbar />);

    await user.upload(screen.getByLabelText(/class json/i), jsonFile("class.json"));
    await user.upload(screen.getByLabelText(/object json/i), jsonFile("object.json"));
    await user.click(screen.getByRole("button", { name: /^import/i }));

    // The same alert spot a refused export uses — one place to look,
    // whichever button was pressed.
    expect(await screen.findByRole("alert")).toHaveTextContent(/import failed/i);
    expect(dispatch).not.toHaveBeenCalled();
  });
});

describe("Toolbar check", () => {
  it("clears a standing result and shows an alert when Check fails", async () => {
    // First a successful check, so the panel reads "No problems found." —
    // then a rejected one. The bug this guards against is exactly that
    // affirmative panel surviving a Check that never actually completed.
    checkDraft.mockResolvedValueOnce([]);
    checkDraft.mockRejectedValueOnce(new Error("validate failed"));
    const user = userEvent.setup();
    render(<Toolbar />);

    await user.click(screen.getByRole("button", { name: /^check$|^prüfen$/i }));
    expect(await screen.findByText(/no problems found|keine probleme/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^check$|^prüfen$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/check failed|prüfung ist fehlgeschlagen/i);
    expect(screen.getByText(/not checked yet|noch nicht geprüft/i)).toBeInTheDocument();
    expect(screen.queryByText(/no problems found|keine probleme/i)).not.toBeInTheDocument();
  });
});
