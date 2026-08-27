import { useEffect, type ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Draft } from "../api/types";
import { DraftProvider, useDraftDispatch } from "../draft/context";
import { emptyDraft } from "../draft/reducer";
import { Card } from "./Card";
import "../i18n";

// The encoder map does not carry every type Google's own enum allows —
// BARCODE_TYPE_UNSPECIFIED is a real value the validator accepts as "a type
// Google knows" but bwip-js has no encoder for.
function draftWithUnmappedBarcodeType(): Draft {
  return {
    ...emptyDraft("loyalty"),
    redemption: {
      redemption_issuers: [],
      smart_tap_enabled: false,
      barcode_type: "BARCODE_TYPE_UNSPECIFIED",
      barcode_value: "12345",
    },
  };
}

// DraftProvider only ever starts from emptyDraft(); a test that needs a
// populated draft has to dispatch replaceDraft into it, the same way an
// import would.
function Setup({ draft, children }: { draft: Draft; children: ReactNode }) {
  const dispatch = useDraftDispatch();
  useEffect(() => {
    dispatch({ type: "replaceDraft", draft });
  }, [dispatch, draft]);
  return <>{children}</>;
}

function renderCard(draft: Draft) {
  return render(
    <DraftProvider>
      <Setup draft={draft}>
        <Card persona={undefined} />
      </Setup>
    </DraftProvider>,
  );
}

describe("Card", () => {
  it("names the symbology it cannot preview, rather than staying silent", async () => {
    renderCard(draftWithUnmappedBarcodeType());

    // A code WAS chosen, so this is neither blank nor the "no code" message —
    // it has to say which type it could not draw.
    expect(
      await screen.findByText(/no preview for BARCODE_TYPE_UNSPECIFIED/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/nfc only/i)).not.toBeInTheDocument();
  });
});
