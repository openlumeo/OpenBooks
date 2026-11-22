// Figures for the Ask example (landing section 6, "ask"). Every value is a string
// produced by code: exact Decimal sums, never typed by hand and never passed through Number().
//
// Source file: web/public/examples/statement.csv (two rows, batch-1).
// Engine run: process() with Params(currency="INR", opening=1000.00, ocr=False, model=False),
// which released the file (status "ok"). The engine tree is packages/py/openbooks/src.
// Command, run from the agent scratchpad folder h5/:
//   python run_engine.py && python figures.py
// figures.py asserts status "ok", a single currency (INR), and opening - debits + credits = closing.
// Its output, pasted verbatim:
//   DEBIT_COUNT 1 / DEBIT_SUM 100.00 INR / DEBIT_IDS txn-00001 / DEBIT_FIRST 2026-01-02 Sample payment txn-00001
//   CREDIT_COUNT 1 / CREDIT_SUM 50.00 INR / CREDIT_IDS txn-00002 / CREDIT_FIRST 2026-01-03 Sample deposit txn-00002
//   TOTAL_ROWS 2 / OPENING 1000.00 CLOSING 950.00 TIES True / BATCH_ID batch-1 / FILE_STATUS ok

export const ASK_EXAMPLE = {
  file: "statement.csv",
  batchId: "batch-1",
  currency: "INR",
  question: "What went out, and what came in?",
  opening: "1000.00",
  closing: "950.00",
  debit: {
    count: 1,
    sum: "100.00",
    ids: ["txn-00001"],
    date: "2026-01-02",
    description: "Sample payment",
  },
  credit: {
    count: 1,
    sum: "50.00",
    ids: ["txn-00002"],
    date: "2026-01-03",
    description: "Sample deposit",
  },
} as const;
