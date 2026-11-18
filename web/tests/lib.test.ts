import { describe, expect, it } from "vitest";
import { parseNDJSON, parseSSE } from "@/lib/sse";
import { fixesFor, stageForRefusal } from "@/lib/stages";
import { batchSummary, columnsFor, groupAmount } from "@/lib/ledger";
import { fileKeys, getEvidence, queryTransactions, type DocRef } from "@/lib/query";
import { buildDigest, FULL_TXN_LIMIT } from "@/lib/digest";
import type { RefusalCode, ReleasedDoc, RefusedDoc, Transaction } from "@/lib/types";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      for (const ch of chunks) c.enqueue(enc.encode(ch));
      c.close();
    },
  });
}

async function collect<T>(it: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const x of it) out.push(x);
  return out;
}

function released(name: string, tx: Partial<Transaction>[], cur = "INR"): ReleasedDoc {
  return {
    schema_version: "openbooks.v1",
    status: "ok",
    file: { sha256: "a".repeat(64), name, detected_format: "csv", layout_version: "bank_csv.v1", method: "parser" },
    data: {
      accounts: [{ id: "acct-1", number: null, currency: cur }],
      parties: [],
      claims: [],
      batches: [{ id: "batch-1", kind: "statement", currency: cur, opening: { amount: "1000.00", currency: cur }, opening_derived: false }],
      transactions: tx.map((t, i) => ({ id: `txn-${String(i + 1).padStart(5, "0")}`, batch_id: "batch-1", ...t })),
    },
    evidence: { "txn-00001.amount": { page: null, bbox: null, row: 2, raw_text: "0.10", method: "parser" } },
    assertions: [{ id: "A1", rule: "r", expected: "x", computed: "x", passed: true, independent: true }],
  };
}

const refused: RefusedDoc = {
  schema_version: "openbooks.v1",
  status: "refused",
  data: null,
  error: { code: "BALANCE_MISMATCH", message: "batch-1: opening + sum(txns) = closing (expected 1.00, got 1.01)", file_sha256: "b".repeat(64) },
};

const m = (amount: string, currency = "INR") => ({ amount, currency });

describe("parseSSE", () => {
  it("reassembles events split across chunks and CRLF", async () => {
    const ev = await collect(parseSSE(streamOf(["event: file.st", "arted\r\ndata: {\"index\":0}\r\n\r\nev", "ent: run.done\ndata: {}\n\n"])));
    expect(ev).toEqual([{ event: "file.started", data: '{"index":0}' }, { event: "run.done", data: "{}" }]);
  });
  it("flushes a final event without a trailing blank line", async () => {
    expect(await collect(parseSSE(streamOf(["event: x\ndata: 1"])))).toEqual([{ event: "x", data: "1" }]);
  });
});

describe("parseNDJSON", () => {
  it("splits lines across chunks", async () => {
    expect(await collect(parseNDJSON(streamOf(['{"a":', '1}\n{"b":2}', "\n"])))).toEqual([{ a: 1 }, { b: 2 }]);
  });
});

describe("stages", () => {
  it("maps every refusal code to the diagram stage it stops at", () => {
    const want: Record<RefusalCode, string> = {
      UNSUPPORTED_INPUT: "detect", UNKNOWN_LAYOUT: "detect", PARSE_ERROR: "parse",
      LOW_CONFIDENCE: "parse", BALANCE_MISMATCH: "balance", OUTPUT_INVALID: "balance",
    };
    for (const [code, stage] of Object.entries(want)) expect(stageForRefusal(code as RefusalCode)).toBe(stage);
  });
  it("finds the fixes the engine asks for", () => {
    expect(fixesFor("statement has no stated opening balance; supply --opening")).toEqual(["opening"]);
    expect(fixesFor("currency not in file; supply --currency")).toEqual(["currency"]);
    expect(fixesFor("row 4: not a number")).toEqual([]);
  });
});

describe("groupAmount", () => {
  it("groups INR in lakhs and others in thousands, keeping every digit", () => {
    expect(groupAmount("12345678.90", "INR")).toBe("1,23,45,678.90");
    expect(groupAmount("-100000.05", "INR")).toBe("-1,00,000.05");
    expect(groupAmount("999.10", "INR")).toBe("999.10");
    expect(groupAmount("1234567.891", "USD")).toBe("1,234,567.891");
    expect(groupAmount("1000", "JPY")).toBe("1,000");
  });
});

describe("ledger", () => {
  it("drops optional columns no row fills", () => {
    const keys = columnsFor("statement", [{ id: "t", batch_id: "b", date: "2026-01-01", direction: "credit", amount: m("1.00") }]).map((c) => c.key);
    expect(keys).toEqual(["date", "credit"]);
  });
  it("summarises a batch with the derived-opening caveat", () => {
    const s = batchSummary({ id: "b", kind: "statement", currency: "INR", period_start: "2026-01-01", period_end: "2026-01-31",
      opening: m("1000.00"), closing: m("1500.00"), opening_derived: true });
    expect(s.map((x) => x.label)).toEqual(["Period", "Opening", "Closing"]);
    expect(s[1]).toMatchObject({ value: "1,000.00 INR", note: "derived, not independent" });
  });
});

describe("queryTransactions", () => {
  const docs: DocRef[] = [
    { file: "a.csv", doc: released("a.csv", [
      { date: "2026-01-01", direction: "debit", amount: m("0.10"), description: "UPI/coffee" },
      { date: "2026-01-02", direction: "debit", amount: m("0.20"), description: "UPI/tea" },
      { date: "2026-01-03", direction: "credit", amount: m("500.00"), description: "NEFT salary" },
    ]) },
    { file: "b.csv", doc: released("b.csv", [{ date: "2026-02-01", direction: "debit", amount: m("1.00", "USD"), description: "upi fx" }], "USD") },
    { file: "c.csv", doc: refused },
  ];

  it("sums exactly in decimal, per currency", () => {
    const r = queryTransactions(docs, { direction: "debit", description_contains: "upi" });
    expect(r.count).toBe(3);
    expect(r.sums).toEqual({ INR: "0.3", USD: "1" });
    expect(r.skipped_refused).toEqual(["c.csv"]);
  });
  it("filters by file, dates and amount bounds", () => {
    expect(queryTransactions(docs, { file: "a.csv", date_from: "2026-01-02", date_to: "2026-01-02" }).rows.map((x) => x.id)).toEqual(["txn-00002"]);
    expect(queryTransactions(docs, { min_amount: "100" }).count).toBe(1);
  });
  it("caps rows but not the count or the sum", () => {
    const r = queryTransactions(docs, { file: "a.csv", limit: 1 });
    expect(r).toMatchObject({ count: 3, truncated: true, sums: { INR: "500.3" } });
    expect(r.rows).toHaveLength(1);
  });
  it("splits count and sums by direction so credits and debits never need hand arithmetic", () => {
    const r = queryTransactions(docs, { file: "a.csv" });
    expect(r.by_direction).toEqual({
      debit: { count: 2, sums: { INR: "0.3" } },
      credit: { count: 1, sums: { INR: "500" } },
    });
  });
  it("returns evidence, and explains refused files", () => {
    expect(getEvidence(docs, "a.csv", "txn-00001", "amount")).toHaveProperty(["txn-00001.amount", "raw_text"], "0.10");
    expect(getEvidence(docs, "c.csv", "txn-00001")).toEqual({ error: "c.csv was refused (BALANCE_MISMATCH); it has no evidence" });
  });
  it("makes duplicate file names addressable", () => {
    expect(fileKeys(["a.csv", "b.csv", "a.csv"])).toEqual(["a.csv", "b.csv", "a.csv #2"]);
  });
});

describe("buildDigest", () => {
  it("leaves out evidence, keeps refusals, and is byte-stable", () => {
    const docs: DocRef[] = [{ file: "a.csv", doc: released("a.csv", [{ date: "2026-01-01", direction: "credit", amount: m("1.00") }]) }, { file: "c.csv", doc: refused }];
    const d = buildDigest(docs);
    expect(d).not.toContain("raw_text");
    expect(d).toContain("BALANCE_MISMATCH");
    expect(buildDigest(docs)).toBe(d);
  });
  it("omits big ledgers and says how to reach them", () => {
    const tx = Array.from({ length: FULL_TXN_LIMIT + 1 }, () => ({ date: "2026-01-01", direction: "credit" as const, amount: m("1.00") }));
    const d = JSON.parse(buildDigest([{ file: "big.csv", doc: released("big.csv", tx) }]));
    expect(d.files[0].transactions).toBeUndefined();
    expect(d.files[0].transactions_note).toMatch(/query_transactions/);
  });
});
