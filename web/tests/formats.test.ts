import { describe, expect, it } from "vitest";
import { batchSummary, columnsFor, KIND_LABEL } from "@/lib/ledger";
import { queryTransactions, rowAmount, type DocRef } from "@/lib/query";
import { fixesFor } from "@/lib/stages";
import { paramSummary } from "@/lib/format";
import type { ReleasedDoc, Transaction } from "@/lib/types";

const usd = (amount: string) => ({ amount, currency: "USD" });

const b1099: Transaction[] = [
  { id: "txn-00001", batch_id: "batch-1", kind: "1099b", description: "100 sh ACME", date: "2026-03-20", date_acquired: "2025-01-15",
    proceeds: usd("1500.00"), cost_basis: usd("1000.00"), gain_loss: usd("500.00"), adjustment: usd("0.00") },
  { id: "txn-00002", batch_id: "batch-1", kind: "1099b", description: "50 sh FOO", date: "2026-04-21",
    proceeds: usd("800.00"), cost_basis: usd("900.00"), gain_loss: usd("-75.00"), adjustment: usd("25.00") },
];

const doc1099: ReleasedDoc = {
  schema_version: "openbooks.v1",
  status: "ok",
  file: { sha256: "c".repeat(64), name: "b.csv", detected_format: "csv", layout_version: "form_1099b.v1", method: "parser" },
  data: {
    accounts: [], parties: [], claims: [], transactions: b1099,
    batches: [{ id: "batch-1", kind: "form_1099b", currency: "USD", period_start: "2026-03-20", period_end: "2026-04-21",
      total_proceeds: usd("2300.00"), total_cost_basis: usd("1900.00"), total_gain_loss: usd("425.00") }],
  },
  evidence: {},
  assertions: [{ id: "A1", rule: "r", expected: "2 rows", computed: "2 rows", passed: true, independent: true }],
};

describe("Form 1099-B", () => {
  it("has its own ledger columns, not the bank statement's", () => {
    expect(columnsFor("form_1099b", b1099).map((c) => c.label)).toEqual(
      ["Sold", "Acquired", "Description", "Proceeds", "Cost basis", "Adjustment", "Gain / loss"],
    );
    expect(columnsFor("form_1099b", b1099).find((c) => c.key === "gain_loss")!.get(b1099[1]!)).toBe("-75.00");
    expect(KIND_LABEL.form_1099b).toBe("Form 1099-B");
  });
  it("shows the printed totals in the batch summary", () => {
    expect(batchSummary(doc1099.data.batches[0]!).map((s) => s.label)).toEqual(
      ["Period", "Printed total proceeds", "Printed total cost basis", "Printed total gain / loss"],
    );
  });
  it("sums gain or loss by default, and any money field on request, exactly", () => {
    const docs: DocRef[] = [{ file: "b.csv", doc: doc1099 }];
    expect(rowAmount(b1099[0]!)).toEqual(usd("500.00"));
    expect(queryTransactions(docs, {}).sums).toEqual({ USD: "425" });
    expect(queryTransactions(docs, { field: "proceeds" }).sums).toEqual({ USD: "2300" });
    expect(queryTransactions(docs, { field: "description" }).sums).toEqual({});
  });
});

describe("date order", () => {
  it("is offered as a fix when the engine asks for it", () => {
    expect(fixesFor("PayPal date column: day/month order is ambiguous; supply --date-order dmy or mdy")).toEqual(["date_order"]);
  });
  it("is named in the params summary", () => {
    expect(paramSummary({ date_order: "mdy" })).toBe("month-first dates");
    expect(paramSummary({ date_order: "dmy", currency: "INR" })).toBe("INR · day-first dates");
  });
});
