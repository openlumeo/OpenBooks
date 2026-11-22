export type LedgerLine = {
  id: string;
  date: string;
  direction: "CR" | "DR";
  description: string;
  amount: string;
  balance: string;
};

export const ENGINE_STAGES = ["Detect", "Parse", "Normalise", "Balance"] as const;

export const RELEASED = {
  sampleId: "ok_bank_csv",
  fileName: "statement.csv",
  currency: "INR",
  periodStart: "2026-01-01",
  periodEnd: "2026-01-08",
  opening: "1000.00",
  closing: "5100.40",
  transactionCount: 8,
  creditTotal: "6857.26",
  debitTotal: "2756.86",
  stagesReached: ["detect", "parse", "normalise", "balance"],
  rows: [
    { id: "txn-00001", date: "2026-01-01", direction: "CR", description: "TXN 0", amount: "1698.81", balance: "2698.81" },
    { id: "txn-00002", date: "2026-01-02", direction: "DR", description: "TXN 1", amount: "2071.01", balance: "627.80" },
    { id: "txn-00003", date: "2026-01-03", direction: "DR", description: "TXN 2", amount: "380.77", balance: "247.03" },
    { id: "txn-00004", date: "2026-01-04", direction: "CR", description: "TXN 3", amount: "494.51", balance: "741.54" },
    { id: "txn-00005", date: "2026-01-05", direction: "DR", description: "TXN 4", amount: "305.08", balance: "436.46" },
  ] satisfies LedgerLine[],
  hiddenRowCount: 3,
  equationAssertion: {
    id: "A1",
    rule: "batch-1: opening + sum(txns) = closing",
    passed: true,
    independent: true,
  },
} as const;

export const TAMPERED = {
  sampleId: "bad_bank_balance_break",
  fileName: "statement-tampered.csv",
  stagesReached: ["detect", "parse", "normalise"],
  failedStage: "Balance",
  code: "BALANCE_MISMATCH",
  message: "batch-1: running balance ties on every row (expected 8 rows, got 7 rows)",
  offendingRowId: "txn-00005",
  offendingPrintedBalance: "436.47",
  offendingComputedBalance: "436.46",
  rows: [
    { id: "txn-00001", date: "2026-01-01", direction: "CR", description: "TXN 0", amount: "1698.81", balance: "2698.81" },
    { id: "txn-00002", date: "2026-01-02", direction: "DR", description: "TXN 1", amount: "2071.01", balance: "627.80" },
    { id: "txn-00003", date: "2026-01-03", direction: "DR", description: "TXN 2", amount: "380.77", balance: "247.03" },
    { id: "txn-00004", date: "2026-01-04", direction: "CR", description: "TXN 3", amount: "494.51", balance: "741.54" },
    { id: "txn-00005", date: "2026-01-05", direction: "DR", description: "TXN 4", amount: "305.08", balance: "436.47" },
  ] satisfies LedgerLine[],
  hiddenRowCount: 3,
} as const;
