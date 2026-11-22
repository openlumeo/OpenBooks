import Decimal from "decimal.js";
import type { EngineDoc, Evidence, Money, ReleasedDoc, Transaction } from "./types";

export type DocRef = { file: string; doc: EngineDoc };

type TxnFilter = {
  file?: string;
  direction?: "credit" | "debit";
  kind?: string;
  description_contains?: string;
  date_from?: string;
  date_to?: string;
  min_amount?: string;
  max_amount?: string;
  field?: string;
  limit?: number;
};

function moneyAt(t: Transaction, k: string): Money | undefined {
  const m = t[k];
  if (m && typeof m === "object" && "amount" in m && "currency" in m
      && typeof m.amount === "string" && /^-?\d+(\.\d+)?$/.test(m.amount)
      && typeof m.currency === "string" && /^[A-Z]{3}$/.test(m.currency)) {
    return { amount: m.amount, currency: m.currency };
  }
  return undefined;
}

export function rowAmount(t: Transaction): Money | undefined {
  for (const k of ["amount", "net", "inr_amount", "reported_value", "gain_loss"] as const) {
    const m = moneyAt(t, k);
    if (m) return m;
  }
  const deb = moneyAt(t, "debit");
  const cre = moneyAt(t, "credit");
  if (deb && cre && deb.currency === cre.currency) {
    const d = new Decimal(deb.amount);
    return { amount: (d.isZero() ? new Decimal(cre.amount) : d.negated()).toFixed(), currency: deb.currency };
  }
  return undefined;
}

type DecimalSum = { coefficient: bigint; scale: number };

function addMoney(sums: Map<string, DecimalSum>, { amount, currency }: Money) {
  const [integer, fraction = ""] = amount.split(".", 2);
  const coefficient = BigInt(integer + fraction);
  const previous = sums.get(currency);
  if (!previous) {
    sums.set(currency, { coefficient, scale: fraction.length });
    return;
  }
  const scale = Math.max(previous.scale, fraction.length);
  sums.set(currency, {
    coefficient: previous.coefficient * 10n ** BigInt(scale - previous.scale)
      + coefficient * 10n ** BigInt(scale - fraction.length),
    scale,
  });
}

function exactSums(sums: Map<string, DecimalSum>): Record<string, string> {
  return Object.fromEntries([...sums].map(([currency, { coefficient, scale }]) => {
    if (scale === 0) return [currency, coefficient.toString()];
    const negative = coefficient < 0n;
    const digits = (negative ? -coefficient : coefficient).toString().padStart(scale + 1, "0");
    const fraction = digits.slice(-scale).replace(/0+$/, "");
    return [currency, (negative ? "-" : "") + digits.slice(0, -scale) + (fraction ? "." + fraction : "")];
  }));
}

type QueryRow = {
  file: string;
  id: string;
  date?: string;
  direction?: string;
  kind?: string;
  description?: string | null;
  reference?: string | null;
  amount?: Money;
};

type QueryResult = {
  count: number;
  sums: Record<string, string>;
  by_direction: Record<string, { count: number; sums: Record<string, string> }>;
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
  const sums = new Map<string, DecimalSum>();
  const byDirection = new Map<string, { count: number; sums: Map<string, DecimalSum> }>();
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
      if (amt) addMoney(sums, amt);
      const bucket = byDirection.get(t.direction ?? "none") ?? { count: 0, sums: new Map<string, DecimalSum>() };
      bucket.count++;
      if (amt) addMoney(bucket.sums, amt);
      byDirection.set(t.direction ?? "none", bucket);
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
    sums: exactSums(sums),
    by_direction: Object.fromEntries(
      [...byDirection].map(([dir, b]) => [dir, { count: b.count, sums: exactSums(b.sums) }]),
    ),
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

export function fileKeys(names: string[]): string[] {
  const used = new Set(names);
  const nextSuffix = new Map<string, number>();
  return names.map((name) => {
    let suffix = nextSuffix.get(name);
    if (suffix === undefined) {
      nextSuffix.set(name, 2);
      return name;
    }
    let key: string;
    do { key = `${name} #${suffix++}`; } while (used.has(key));
    nextSuffix.set(name, suffix);
    used.add(key);
    return key;
  });
}
