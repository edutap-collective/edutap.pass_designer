import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DraftProvider } from "../draft/context";
import { ModuleList } from "./ModuleList";
import "../i18n";

function renderList() {
  return render(
    <DraftProvider>
      <ModuleList
        catalogue={[{ key: "person.display_name", value_type: "text", required: false }]}
      />
    </DraftProvider>,
  );
}

describe("ModuleList", () => {
  it("says that modules are shared by every view", () => {
    renderList();

    // The single most direct way to break a template is to believe a module
    // belongs to the tab you are looking at. The interface has to say so.
    expect(screen.getByText(/shared by every view|geteilt/i)).toBeInTheDocument();
  });

  it("adds a module and lets it be switched to a bound value", async () => {
    const user = userEvent.setup();
    renderList();

    await user.click(screen.getByRole("button", { name: /add module|Modul hinzufügen/i }));
    await user.type(screen.getByLabelText(/header|kopfzeile/i), "Name");
    await user.click(screen.getByLabelText(/filled per person|je person/i));

    expect(screen.getByRole("combobox", { name: /field|feld/i })).toBeInTheDocument();
  });
});
