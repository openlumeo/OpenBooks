// Real evidence record for the Trace section.
//
// Sample id: ok_pdf_text (synthetic, text-layer bank statement PDF, golden set seed 7).
// Produced by the engine, not written by hand:
//   build(Path("golden"), seed=7, scans=False)      # openbooks_lab.golden
//   process(Path("golden/ok_pdf_text/in.pdf"),
//           Params(currency="INR", opening=Decimal("1000.00")))   # openbooks.pipeline
// Status "ok", layout bank_statement_pdf.v1, method pdf_text. Values below are copied verbatim
// from that output: transaction txn-00001 and evidence keys txn-00001.{date,amount,balance_after}.
// Amounts stay decimal strings; raw_text is the printed form as the engine read it.
// Engine run used a scratch entry-point registration built from packages/py/openbooks/pyproject.toml
// because the editable install in this checkout does not register the layout providers.

export type TraceMoney = { amount: string; currency: string };

/** [x0, y0, x1, y1] exactly as the engine emits it. */
export type TraceBBox = [number, number, number, number];

export type TraceTransaction = {
  id: string;
  batch_id: string;
  account_id: string;
  date: string;
  direction: "credit" | "debit";
  amount: TraceMoney;
  balance_after: TraceMoney;
  description: string | null;
  reference: string | null;
};

export type TraceEvidence = {
  /** Evidence key in the document, e.g. "txn-00001.amount". */
  key: string;
  page: number | null;
  bbox: TraceBBox | null;
  row: number | null;
  raw_text: string;
  method: string;
  confidence?: number;
};

export type TraceSample = {
  sampleId: string;
  filename: string;
  status: "ok";
  layoutVersion: string;
  detectedFormat: string;
  method: string;
  transaction: TraceTransaction;
  evidence: readonly TraceEvidence[];
};

export const TRACE_SAMPLE: TraceSample = {
  sampleId: "ok_pdf_text",
  filename: "in.pdf",
  status: "ok",
  layoutVersion: "bank_statement_pdf.v1",
  detectedFormat: "pdf",
  method: "pdf_text",
  transaction: {
    id: "txn-00001",
    batch_id: "batch-1",
    account_id: "acct-1",
    date: "2026-01-01",
    direction: "credit",
    amount: { amount: "2226.70", currency: "INR" },
    balance_after: { amount: "3226.70", currency: "INR" },
    description: "ATM WDL 208061 MUMBAI 753159",
    reference: null,
  },
  evidence: [
    {
      key: "txn-00001.date",
      page: 1,
      bbox: [38.0, 99.4, 83.0, 109.4],
      row: 1,
      raw_text: "01/01/2026",
      method: "pdf_text",
    },
    {
      key: "txn-00001.amount",
      page: 1,
      bbox: [424.0, 99.4, 459.0, 109.4],
      row: 1,
      raw_text: "2,226.70",
      method: "pdf_text",
    },
    {
      key: "txn-00001.balance_after",
      page: 1,
      bbox: [512.0, 99.4, 547.0, 109.4],
      row: 1,
      raw_text: "3,226.70",
      method: "pdf_text",
    },
  ],
};
