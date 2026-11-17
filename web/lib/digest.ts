// What the Q&A model sees about a thread's documents. Evidence maps are left out (reachable by tool);
// big ledgers are left out (reachable by tool). Keys are sorted so the digest is byte-stable for caching.
import type { DocRef } from "./query";

export const FULL_TXN_LIMIT = 200;

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
    const tx = doc.data.transactions;
    return {
      file,
      status: "released",
      layout: doc.file.layout_version,
      format: doc.file.detected_format,
      method: doc.file.method,
      accounts: doc.data.accounts,
      batches: doc.data.batches,
      assertions: doc.assertions,
      transaction_count: tx.length,
      transactions: tx.length <= FULL_TXN_LIMIT ? tx : undefined,
      transactions_note: tx.length > FULL_TXN_LIMIT ? `omitted (${tx.length} rows); use query_transactions` : undefined,
    };
  });
  return JSON.stringify(stable({ schema: "openbooks.v1 digest", files }));
}
