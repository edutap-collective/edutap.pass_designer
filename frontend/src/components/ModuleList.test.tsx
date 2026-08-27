import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DraftProvider } from "../draft/context";
import { ModuleList, nextTextModuleId } from "./ModuleList";
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

describe("nextTextModuleId", () => {
  it("does not repeat an id an imported artefact left with a gap in its numbering", () => {
    // An artefact carrying only `module_2` is exactly what a foreign class
    // looks like once imported — Import exists to take foreign artefacts.
    // `module_${length + 1}` would compute `module_2` again here (length 1)
    // and silently merge the new module into the imported one.
    const id = nextTextModuleId([{ module_id: "module_2", value: "", bound: false }]);

    expect(id).not.toBe("module_2");
    expect(id).toBe("module_3");
  });

  it("starts at module_1 for an empty draft", () => {
    expect(nextTextModuleId([])).toBe("module_1");
  });

  it("ignores ids outside the module_N pattern", () => {
    const id = nextTextModuleId([{ module_id: "imported-legacy-id", value: "", bound: false }]);

    expect(id).toBe("module_1");
  });
});
