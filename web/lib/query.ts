// Deterministic answers for the Q&A model. The model never adds money; these functions do,
// in decimal.js over the engine's decimal strings, and return exact strings.
import Decimal from "decimal.js";
import type { EngineDoc, Evidence, Money, ReleasedDoc, Transaction } from "./types";

export type DocRef = { file: string; doc: EngineDoc };

export type TxnFilter = {
  file?: string;
  direction?: "credit" | "debit";
  kind?: string;
  description_contains?: string;
  date_from?: string;
  date_to?: string;
  min_amount?: string;
  max_amount?: string;
  /** sum this money field instead of the row's default amount, e.g. proceeds, cost_basis, fee, tax_deducted */
  field?: string;
  limit?: number;
};

function moneyAt(t: Transaction, k: string): Money | undefined {
  const m = t[k];
  return m && typeof m === "object" && "amount" in m && "currency" in m ? (m as Money) : undefined;
}

/** The single money value that represents a row's size, per batch kind:
 *  amount (statements), net (settlements), inr_amount (FIRA), reported_value (AIS), gain_loss (1099-B),
 *  or debit/credit (trial balance, debits negative). */
export function rowAmount(t: Transaction): Money | undefined {
  for (const k of ["amount", "net", "inr_amount", "reported_value", "gain_loss"] as const) {
    const m = moneyAt(t, k);
    if (m) return m;
  }
  const deb = t.debit as Money | undefined;
  const cre = t.credit as Money | undefined;
  if (deb && cre) {
    const d = new Decimal(deb.amount);
    return { amount: (d.isZero() ? new Decimal(cre.amount) : d.negated()).toFixed(), currency: deb.currency };
  }
  return undefined;
}

export type QueryRow = {
  file: string;
  id: string;
  date?: string;
  direction?: string;
  kind?: string;
  description?: string | null;
  reference?: string | null;
  amount?: Money;
};

export type QueryResult = {
  count: number;
  /** exact decimal strings, one per currency */
  sums: Record<string, string>;
  rows: QueryRow[];
  truncated: boolean;
  skipped_refused: string[];
};

function released(docs: DocRef[], file?: string): { file: string; doc: ReleasedDoc }[] {
  return docs.filter((d): d is { file: string; doc: ReleasedDoc } => d.doc.status === "ok" && (!file || d.file === file));
}

export function queryTransactions(docs: DocRef[], f: TxnFilter): QueryResult {
  const limit = Math.min(Math.max(f.limit ?? 50, 1), 200);
  const needle = f.description_contains?.toLowerCase();
  const min = f.min_amount !== undefined ? new Decimal(f.min_amount) : undefined;
  const max = f.max_amount !== undefined ? new Decimal(f.max_amount) : undefined;
  const sums = new Map<string, Decimal>();
  const rows: QueryRow[] = [];
  let count = 0;
  for (const { file, doc } of released(docs, f.file)) {
    for (const t of doc.data.transactions) {
      if (f.direction && t.direction !== f.direction) continue;
      if (f.kind && t.kind !== f.kind) continue;
      if (f.date_from && (!t.date || t.date < f.date_from)) continue;
      if (f.date_to && (!t.date || t.date > f.date_to)) continue;
      if (needle) {
        const hay = `${t.description ?? ""} ${t.reference ?? ""} ${t.kind ?? ""} ${t.deductor ?? ""} ${t.remitter ?? ""} ${t.account ?? ""} ${t.category ?? ""}`.toLowerCase();
        if (!hay.includes(needle)) continue;
      }
      const amt = f.field ? moneyAt(t, f.field) : rowAmount(t);
      if (min || max) {
        if (!amt) continue;
        const a = new Decimal(amt.amount).abs();
        if (min && a.lt(min)) continue;
        if (max && a.gt(max)) continue;
      }
      count++;
      if (amt) sums.set(amt.currency, (sums.get(amt.currency) ?? new Decimal(0)).plus(amt.amount));
      if (rows.length < limit) {
        rows.push({
          file, id: t.id, date: t.date, direction: t.direction, kind: t.kind,
          description: t.description ?? (t.deductor as string | undefined) ?? (t.account as string | undefined) ?? null,
          reference: t.reference ?? null, amount: amt,
        });
      }
    }
  }
  return {
    count,
    sums: Object.fromEntries([...sums].map(([c, d]) => [c, d.toFixed()])),
    rows,
    truncated: count > rows.length,
    skipped_refused: docs.filter((d) => d.doc.status === "refused" && (!f.file || d.file === f.file)).map((d) => d.file),
  };
}

export function getEvidence(docs: DocRef[], file: string, recordId: string, field?: string): Record<string, Evidence> | { error: string } {
  const hit = docs.find((d) => d.file === file);
  if (!hit) return { error: `no file named ${file}` };
  if (hit.doc.status !== "ok") return { error: `${file} was refused (${hit.doc.error.code}); it has no evidence` };
  const prefix = field ? `${recordId}.${field}` : `${recordId}.`;
  const out = Object.fromEntries(
    Object.entries(hit.doc.evidence).filter(([k]) => (field ? k === prefix : k.startsWith(prefix))),
  );
  return Object.keys(out).length ? out : { error: `no evidence for ${prefix}${field ? "" : "*"} in ${file}` };
}

/** Distinct file keys for a thread's docs. Same name twice gets a #2 suffix so the model can address each. */
export function fileKeys(names: string[]): string[] {
  const seen = new Map<string, number>();
  return names.map((n) => {
    const k = (seen.get(n) ?? 0) + 1;
    seen.set(n, k);
    return k === 1 ? n : `${n} #${k}`;
  });
}
