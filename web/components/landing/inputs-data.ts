export type InputGroup = {
  id: "statements" | "gateways" | "tax" | "workpapers";
  title: string;
  inputs: readonly string[];
  layouts: readonly string[];
  extensions: readonly string[];
  note?: string;
};

export const INPUT_GROUPS: readonly InputGroup[] = [
  {
    id: "statements",
    title: "Bank statements",
    inputs: ["CSV", "OFX / QFX", "MT940", "PDF (text layer)", "Scans (OCR)", "Wise statement"],
    layouts: ["bank_csv.v1", "ofx.v1", "mt940.v1", "bank_statement_pdf.v1", "wise_statement.v1"],
    extensions: [".csv", ".ofx", ".qfx", ".sta", ".mt940", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".xlsx"],
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

export const UNVERIFIED: readonly { layout: string; name: string }[] = [
  { layout: "paypal_activity.v1", name: "PayPal activity" },
  { layout: "wise_statement.v1", name: "Wise statement" },
  { layout: "form_1099b.v1", name: "Form 1099-B" },
];

export const UNVERIFIED_NOTE = "Built to the published export format. Not yet validated on files from the wild.";

export const SIZE_NOTE = "Limit 20 MB per file.";
