// Input groups and layouts for the Inputs section.
// Copied by hand from server/openbooks_server/catalog.py: FORMATS (group ids, titles, inputs,
// layouts, extensions) and UNVERIFIED (layout ids and names). Do not add formats here that are
// not in catalog.py. server/tests/test_server.py checks the layout ids against the engine source.

export type InputGroup = {
  id: "statements" | "gateways" | "tax" | "workpapers";
  title: string;
  /** Human-readable input names, from catalog.py `inputs`. */
  inputs: readonly string[];
  /** Layout ids, from catalog.py `layouts`. */
  layouts: readonly string[];
  /** From catalog.py `extensions`. */
  extensions: readonly string[];
  /** Optional note, sourced from PRODUCT.md (Capabilities and Constraints). */
  note?: string;
};

export const INPUT_GROUPS: readonly InputGroup[] = [
  {
    id: "statements",
    title: "Bank statements",
    inputs: ["CSV", "OFX / QFX", "MT940", "PDF (text layer)", "Scans (OCR)", "Wise statement"],
    layouts: ["bank_csv.v1", "ofx.v1", "mt940.v1", "bank_statement_pdf.v1", "wise_statement.v1"],
    extensions: [".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".xlsx"],
    // PRODUCT.md: "bank statements (CSV and PDF) default to day-first without proof".
    note: "Day-first dates are assumed for bank statements; you can set the order per file.",
  },
  {
    id: "gateways",
    title: "Gateway settlements",
    inputs: ["Stripe balance export", "Razorpay settlement", "PayPal activity"],
    layouts: ["stripe_balance.v1", "razorpay_settlement.v1", "paypal_activity.v1"],
    extensions: [".csv", ".xlsx"],
  },
  {
    id: "tax",
    title: "Tax documents",
    inputs: ["Form 26AS (TDS)", "AIS", "FIRA", "Form 1099-B"],
    layouts: ["tds_26as.v1", "ais.v1", "fira.v1", "form_1099b.v1"],
    extensions: [".csv", ".xlsx"],
  },
  {
    id: "workpapers",
    title: "Excel workpapers",
    inputs: ["Trial balance", "Any layout above, as .xlsx"],
    layouts: ["trial_balance.v1"],
    extensions: [".csv", ".xlsx"],
  },
];

/** catalog.py UNVERIFIED: layouts built from public descriptions, tested on synthetic files only. */
export const UNVERIFIED: readonly { layout: string; name: string }[] = [
  { layout: "paypal_activity.v1", name: "PayPal activity" },
  { layout: "wise_statement.v1", name: "Wise statement" },
  { layout: "form_1099b.v1", name: "Form 1099-B" },
];

/** Shown under the PREVIEW tag. */
export const UNVERIFIED_NOTE = "Built to the published export format. Not yet validated on files from the wild.";

/** Size limit, from PRODUCT.md (catalog.py max_bytes is 20 MB). */
export const SIZE_NOTE = "Limit 20 MB per file.";
