import type { DocRef } from "./query";

function stable(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(stable);
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.keys(v as object).sort().map((k) => [k, stable((v as Record<string, unknown>)[k])]));
  }
  return v;
}

export function buildDigest(docs: DocRef[]): string {
  const files = docs.map(({ file, doc }) => {
    if (doc.status === "refused") {
      return { file, status: "refused", refusal: { code: doc.error.code, message: doc.error.message } };
    }
    return {
      file,
      status: "released",
      layout: doc.file.layout_version,
      format: doc.file.detected_format,
      method: doc.file.method,
      accounts: doc.data.accounts,
      batches: doc.data.batches,
      assertions: doc.assertions.map(({ id, rule, passed, independent }) => ({ id, rule, passed, independent })),
      transaction_count: doc.data.transactions.length,
      transactions_note: "Use query_transactions for all transaction rows, totals, and filtered counts.",
    };
  });
  return promptJson(stable({ schema: "openbooks.v1 digest", files }));
}

function promptJson(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e");
}
