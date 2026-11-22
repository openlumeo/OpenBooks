import type { DocRef } from "./query";

export const FULL_TXN_LIMIT = 200;
const INLINE_TXN_BYTES = 32 * 1024;

function stable(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(stable);
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.keys(v as object).sort().map((k) => [k, stable((v as Record<string, unknown>)[k])]));
  }
  return v;
}

export function buildDigest(docs: DocRef[]): string {
  const encoder = new TextEncoder();
  let remaining = INLINE_TXN_BYTES;
  const files = docs.map(({ file, doc }) => {
    if (doc.status === "refused") {
      return { file, status: "refused", refusal: { code: doc.error.code, message: doc.error.message } };
    }
    const tx = doc.data.transactions;
    const bytes = tx.length <= FULL_TXN_LIMIT ? encoder.encode(promptJson(tx)).byteLength : Infinity;
    const inline = bytes <= remaining;
    if (inline) remaining -= bytes;
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
      transactions: inline ? tx : undefined,
      transactions_note: inline ? undefined : `omitted (${tx.length} rows); use query_transactions`,
    };
  });
  return promptJson(stable({ schema: "openbooks.v1 digest", files }));
}

function promptJson(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e");
}
