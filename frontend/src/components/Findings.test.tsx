import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Finding } from "../api/types";
import { Findings } from "./Findings";
import i18n from "../i18n";

const errorFinding: Finding = {
  location: "head.programLogo",
  message: "Google requires 'programLogo' when the class is created.",
  severity: "error",
};

const warningFinding: Finding = {
  location: "front_rows[0]",
  message: "This row has an empty cell.",
  severity: "warning",
};

describe("Findings", () => {
  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  // `null` is "not checked yet". `[]` is "checked and clean". Conflating them
  // would let an unchecked draft look approved — the property this whole
  // task exists to surface, so it gets its own three assertions rather than
  // being folded into a single "renders" test.
  it("says the draft has not been checked yet when findings is null", () => {
    render(<Findings findings={null} />);

    expect(screen.getByText(/not checked yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/no problems found/i)).not.toBeInTheDocument();
  });

  it("says no problems were found when findings is an empty array", () => {
    render(<Findings findings={[]} />);

    expect(screen.getByText(/no problems found/i)).toBeInTheDocument();
    expect(screen.queryByText(/not checked yet/i)).not.toBeInTheDocument();
  });

  it("lists findings with errors before warnings", () => {
    render(<Findings findings={[warningFinding, errorFinding]} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(errorFinding.location);
    expect(items[0]).toHaveTextContent(/error/i);
    expect(items[1]).toHaveTextContent(warningFinding.location);
    expect(items[1]).toHaveTextContent(/warning/i);
  });

  // The list's accessible name has to describe the list as a whole, not
  // repeat the "Error" per-item prefix — a warnings-only list is not an
  // error list.
  it("names the list 'Findings' rather than 'Error', regardless of severity", () => {
    render(<Findings findings={[warningFinding]} />);

    expect(screen.getByRole("list", { name: /findings/i })).toBeInTheDocument();
  });

  // A hard-coded English string would pass every assertion above just as
  // well as a translated one. Only switching the interface language and
  // reading a real finding catches a missing or wrong translation.
  it("reads a finding in German when the interface is German", async () => {
    await i18n.changeLanguage("de");
    render(<Findings findings={[errorFinding]} />);

    expect(screen.getByRole("list", { name: "Befunde" })).toBeInTheDocument();
    expect(screen.getByText("Fehler")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent(errorFinding.message);
    expect(screen.queryByText("Findings")).not.toBeInTheDocument();
  });
});
