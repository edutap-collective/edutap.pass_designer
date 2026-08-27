import { useEffect, useRef } from "react";
import bwipjs from "@bwip-js/browser";
import { useTranslation } from "react-i18next";
import type { Persona } from "../api/types";
import { useDraft } from "../draft/context";
import { resolvePlaceholders } from "./resolve";
import "./Card.css";

// Google's barcode symbologies, mapped to the BWIPP encoder that draws them.
// TEXT_ONLY draws no code by definition and is correctly absent here. A type
// Google defines but this map does not carry (e.g. the unspecified default)
// is never drawn wrong — the render below says explicitly that it cannot
// preview that type, rather than staying silent about a code that was
// actually chosen.
const ENCODERS: Record<string, string> = {
  AZTEC: "azteccode",
  CODE_39: "code39",
  CODE_128: "code128",
  CODABAR: "rationalizedCodabar",
  DATA_MATRIX: "datamatrix",
  EAN_8: "ean8",
  EAN_13: "ean13",
  ITF_14: "itf14",
  PDF_417: "pdf417",
  QR_CODE: "qrcode",
  UPC_A: "upca",
};

export function Card({ persona }: { persona: Persona | undefined }) {
  const draft = useDraft();
  const { t } = useTranslation();
  const values = persona?.values ?? {};
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const textOf = (moduleId: string | undefined): string => {
    const module = draft.text_modules.find((m) => m.module_id === moduleId);
    if (!module) return "";
    // A bound value is resolved against the persona; a constant is shown as
    // it is. Both take the same path the pass builder takes at issuing time.
    return module.bound
      ? resolvePlaceholders(`\${${module.value}}`, values)
      : module.value;
  };

  const headerOf = (moduleId: string | undefined): string =>
    draft.text_modules.find((m) => m.module_id === moduleId)?.header ?? "";

  const barcodeType = draft.redemption.barcode_type;
  const encoder = barcodeType ? ENCODERS[barcodeType] : undefined;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !encoder) return;

    // A fake code would be a falsehood at exactly the spot a designer looks
    // at, and it would misstate the footprint — which is what actually moves
    // the layout. So this always draws the real value, never a stock image.
    try {
      bwipjs.toCanvas(canvas, {
        bcid: encoder,
        text: draft.redemption.barcode_value || " ",
        includetext: false,
      });
    } catch {
      // A value the chosen symbology cannot encode (wrong length, bad check
      // digit, an empty string, …) is a data problem the export validation
      // already reports elsewhere. The preview just leaves the canvas blank
      // rather than showing a broken or stale drawing.
      const context = canvas.getContext("2d");
      context?.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, [encoder, draft.redemption.barcode_value]);

  return (
    <div
      className="card"
      style={{ background: draft.head.hexBackgroundColor || "#4285f4" }}
    >
      {draft.head.programLogo ? (
        <img className="card__logo" src={draft.head.programLogo} alt="" />
      ) : null}
      <div className="card__issuer">{draft.head.issuerName}</div>
      <div className="card__program">{draft.head.programName}</div>

      {draft.front_rows.map((row, rowIndex) => (
        <div
          key={rowIndex}
          className="card__row"
          style={{ gridTemplateColumns: `repeat(${row.cells.length}, 1fr)` }}
        >
          {row.cells.map((cell, cellIndex) => {
            const moduleId = cell.first?.fallback_chain[0]?.module_id;
            return (
              <div key={cellIndex} className="card__cell">
                <div className="card__label">{headerOf(moduleId)}</div>
                <div className="card__value">{textOf(moduleId)}</div>
              </div>
            );
          })}
        </div>
      ))}

      {/* NFC without a visible code is the normal case — these are identity
          and library cards read by a terminal, not scanned. Its absence
          moves the layout, so it is shown rather than reserving space for
          it, but only when no symbology was chosen at all. A symbology the
          encoder map does not carry is a different situation — a code WAS
          chosen — so it says as much rather than staying silent (which
          would read as a bug, not a decision) or drawing something wrong. */}
      {barcodeType && encoder ? (
        <canvas ref={canvasRef} className="card__code" data-testid="card-code" />
      ) : barcodeType ? (
        <div className="card__nocode">
          {t("preview.unsupportedCode", { type: barcodeType })}
        </div>
      ) : (
        <div className="card__nfc">
          {/* The contactless mark, drawn at the position a barcode would
              occupy. It keeps the layout consequence of having no code
              visible — the point the spec makes about this being the normal
              case — and states it in the vernacular of the object itself:
              this pass is tapped, not scanned. Decorative, so it is hidden
              from the accessibility tree; the caption carries the meaning. */}
          <svg
            className="card__nfc-mark"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <path d="M6.57 8.94A4 4 0 0 1 6.57 15.06" />
            <path d="M8.5 6.64A7 7 0 0 1 8.5 17.36" />
            <path d="M10.43 4.34A10 10 0 0 1 10.43 19.66" />
            <path d="M12.36 2.04A13 13 0 0 1 12.36 21.96" />
          </svg>
          <span>{t("preview.noCode")}</span>
        </div>
      )}
    </div>
  );
}
