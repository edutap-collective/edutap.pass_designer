import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { DraftProvider } from "../draft/context";
import { FrontRows } from "./FrontRows";
import i18n from "../i18n";

function renderRows() {
  return render(
    <DraftProvider>
      <FrontRows />
    </DraftProvider>,
  );
}

describe("FrontRows", () => {
  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  // A hard-coded label passes an English-only assertion just as well as a
  // translated one. Switching the interface language and asserting the
  // German string is the only check that actually distinguishes them — it
  // catches every hard-coded aria-label in this component, not just one.
  it("names row and cell controls in German when the interface is German", async () => {
    await i18n.changeLanguage("de");
    const user = userEvent.setup();
    renderRows();

    await user.click(screen.getByRole("button", { name: /zeile hinzufügen/i }));

    expect(screen.getByRole("combobox", { name: "Zeile 1" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Zeile 1, Zelle 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zeile 1 entfernen" })).toBeInTheDocument();

    // Not present in either language — the class of bug under test.
    expect(screen.queryByRole("combobox", { name: /^Row 1$/ })).not.toBeInTheDocument();
  });

  it("names row and cell controls in English when the interface is English", async () => {
    await i18n.changeLanguage("en");
    const user = userEvent.setup();
    renderRows();

    await user.click(screen.getByRole("button", { name: /add row/i }));

    expect(screen.getByRole("combobox", { name: "Row 1" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Row 1, cell 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove row 1" })).toBeInTheDocument();
  });
});
