export type TraceMoney = { amount: string; currency: string };

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
