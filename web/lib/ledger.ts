import type { Batch, BatchKind, Money, Transaction } from "./types";

/**
 * Group the integer part of a decimal string for display, without ever parsing it as a float.
 * INR uses Indian grouping (1,23,45,678.90); everything else groups by thousands.
 * The digits, sign and decimals are exactly the engine's.
 */
export function groupAmount(amount: string, currency?: string): string {
  const neg = amount.startsWith("-");
  const body = neg ? amount.slice(1) : amount;
  const [int = "0", frac] = body.split(".");
  let grouped: string;
  if (currency === "INR" && int.length > 3) {
    const head = int.slice(0, -3);
    const tail = int.slice(-3);
    grouped = head.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + tail;
  } else {
    grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
  return (neg ? "-" : "") + grouped + (frac !== undefined ? "." + frac : "");
}

export function fmtMoney(m: Money | null | undefined): string {
  return m ? groupAmount(m.amount, m.currency) : "";
}

export type Column = {
  key: string;
  label: string;
  numeric?: boolean;
  /** evidence field name for this column, when one exists */
  field?: string;
  get: (t: Transaction) => string;
};

const money = (k: string) => (t: Transaction) => fmtMoney(t[k] as Money | undefined);
const text = (k: string) => (t: Transaction) => {
  const v = t[k];
  return v === null || v === undefined ? "" : String(v);
};

const DATE: Column = { key: "date", label: "Date", field: "date", get: text("date") };

export const COLUMNS: Record<BatchKind, Column[]> = {
  statement: [
    DATE,
    { key: "description", label: "Description", get: text("description") },
    { key: "reference", label: "Ref", get: text("reference") },
    { key: "debit", label: "Debit", numeric: true, field: "amount", get: (t) => (t.direction === "debit" ? fmtMoney(t.amount) : "") },
    { key: "credit", label: "Credit", numeric: true, field: "amount", get: (t) => (t.direction === "credit" ? fmtMoney(t.amount) : "") },
    { key: "balance_after", label: "Balance", numeric: true, field: "balance_after", get: money("balance_after") },
  ],
  settlement: [
    DATE,
    { key: "kind", label: "Type", get: text("kind") },
    { key: "reference", label: "Ref", get: text("reference") },
    { key: "gross", label: "Gross", numeric: true, field: "gross", get: money("gross") },
    { key: "fee", label: "Fee", numeric: true, field: "fee", get: money("fee") },
    { key: "tax", label: "Tax", numeric: true, field: "tax", get: money("tax") },
    { key: "net", label: "Net", numeric: true, field: "net", get: money("net") },
  ],
  tax_statement: [
    DATE,
    { key: "deductor", label: "Deductor", get: text("deductor") },
    { key: "tan", label: "TAN", get: text("tan") },
    { key: "section", label: "Section", get: text("section") },
    { key: "amount", label: "Paid / credited", numeric: true, field: "amount", get: money("amount") },
    { key: "tax_deducted", label: "TDS deducted", numeric: true, field: "tax_deducted", get: money("tax_deducted") },
    { key: "tax_deposited", label: "TDS deposited", numeric: true, field: "tax_deposited", get: money("tax_deposited") },
  ],
  ais: [
    DATE,
    { key: "category", label: "Category", get: text("category") },
    { key: "description", label: "Description", get: text("description") },
    { key: "source", label: "Source", get: text("source") },
    { key: "reported_value", label: "Reported", numeric: true, field: "reported_value", get: money("reported_value") },
    { key: "modified_value", label: "Modified", numeric: true, field: "modified_value", get: money("modified_value") },
  ],
  fira: [
    DATE,
    { key: "reference", label: "FIRA no.", get: text("reference") },
    { key: "remitter", label: "Remitter", get: text("remitter") },
    { key: "foreign_amount", label: "Foreign", numeric: true, field: "foreign_amount", get: (t) => {
      const m = t.foreign_amount as Money | undefined;
      return m ? `${fmtMoney(m)} ${m.currency}` : "";
    } },
    { key: "exchange_rate", label: "Rate", numeric: true, field: "exchange_rate", get: text("exchange_rate") },
    { key: "inr_amount", label: "INR", numeric: true, field: "inr_amount", get: money("inr_amount") },
    { key: "bank_charges", label: "Charges", numeric: true, field: "bank_charges", get: money("bank_charges") },
    { key: "net_credited", label: "Net credited", numeric: true, field: "net_credited", get: money("net_credited") },
  ],
  form_1099b: [
    { key: "date", label: "Sold", field: "date", get: text("date") },
    { key: "date_acquired", label: "Acquired", field: "date_acquired", get: text("date_acquired") },
    { key: "description", label: "Description", get: text("description") },
    { key: "proceeds", label: "Proceeds", numeric: true, field: "proceeds", get: money("proceeds") },
    { key: "cost_basis", label: "Cost basis", numeric: true, field: "cost_basis", get: money("cost_basis") },
    { key: "adjustment", label: "Adjustment", numeric: true, field: "adjustment", get: money("adjustment") },
    { key: "gain_loss", label: "Gain / loss", numeric: true, field: "gain_loss", get: money("gain_loss") },
  ],
  trial_balance: [
    { key: "account", label: "Account", get: text("account") },
    { key: "debit", label: "Debit", numeric: true, field: "debit", get: money("debit") },
    { key: "credit", label: "Credit", numeric: true, field: "credit", get: money("credit") },
  ],
};

/** Columns for a batch, dropping optional columns no row fills (e.g. FIRA without charges). */
export function columnsFor(kind: BatchKind, rows: Transaction[]): Column[] {
  const cols = COLUMNS[kind] ?? COLUMNS.statement;
  return cols.filter((c) => c.key === "date" ? rows.some((r) => r.date) : rows.some((r) => c.get(r) !== ""));
}

export const KIND_LABEL: Record<BatchKind, string> = {
  statement: "Bank statement",
  settlement: "Settlement",
  tax_statement: "Form 26AS (TDS)",
  ais: "AIS",
  fira: "FIRA",
  trial_balance: "Trial balance",
  form_1099b: "Form 1099-B",
};

const SUMMARY: [string, string][] = [
  ["opening", "Opening"],
  ["closing", "Closing"],
  ["stated_closing", "Printed closing"],
  ["payout", "Payout"],
  ["total_amount", "Printed total paid"],
  ["total_tax_deducted", "Printed total TDS"],
  ["total_tax_deposited", "Printed total deposited"],
  ["total_reported_value", "Printed total reported"],
  ["total_inr_amount", "Printed total INR"],
  ["total_net_credited", "Printed total net"],
  ["total_debit", "Printed total debit"],
  ["total_credit", "Printed total credit"],
  ["total_proceeds", "Printed total proceeds"],
  ["total_cost_basis", "Printed total cost basis"],
  ["total_gain_loss", "Printed total gain / loss"],
];

/** Label/value pairs for the batch header, in a stable order, only for fields the batch has. */
export function batchSummary(b: Batch): { key: string; label: string; value: string; note?: string }[] {
  const out: { key: string; label: string; value: string; note?: string }[] = [];
  if (b.period_start || b.period_end) {
    out.push({ key: "period", label: "Period", value: b.period_start === b.period_end ? `${b.period_start}` : `${b.period_start} – ${b.period_end}` });
  }
  for (const [k, label] of SUMMARY) {
    const m = b[k] as Money | null | undefined;
    if (m && typeof m === "object" && "amount" in m) {
      out.push({
        key: k,
        label,
        value: `${fmtMoney(m)} ${m.currency}`,
        note: k === "opening" && b.opening_derived ? "derived, not independent" : undefined,
      });
    }
  }
  return out;
}
