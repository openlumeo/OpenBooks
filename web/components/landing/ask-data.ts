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

export const ASK_FOLLOW_UP = {
  question: "How many credits?",
} as const;
