// Data for the live demo. Pure, server-safe. Amounts stay decimal strings from the engine: never Number().
import { stageForRefusal } from "@/lib/stages";
import type { EngineDoc, RefusalCode, Stage } from "@/lib/types";
import { RELEASED, TAMPERED } from "./proof-data";

/** A ledger row as the demo draws it. Direction is CR, DR, or empty when the engine omits it. */
export type DemoRow = { id: string; date: string; direction: string; description: string; amount: string; balance: string };

export type DemoSampleId = "ok_bank_csv" | "bad_bank_balance_break";

/** The two chips. Labels are the visitor-facing names; ids are the engine's golden-set case ids. */
export const DEMO_SAMPLES: readonly { id: DemoSampleId; chip: string }[] = [
  { id: "ok_bank_csv", chip: "statement.csv" },
  { id: "bad_bank_balance_break", chip: "statement.csv, one balance altered" },
];

export function isDemoSampleId(value: string): value is DemoSampleId {
  return DEMO_SAMPLES.some((s) => s.id === value);
}

export type CheckLine = { id: string; rule: string; passed: boolean; independent: boolean };

export type DemoVerdict =
  | {
      kind: "released";
      currency: string;
      opening: string;
      closing: string;
      rowCount: number;
      rows: DemoRow[];
      hiddenRowCount: number;
      checks: CheckLine[];
    }
  | { kind: "refused"; code: RefusalCode; message: string; stopAt: Stage };

/** Rows shown in the ledger before the rest are counted. */
export const LEDGER_PREVIEW = 5;

/** Map a live engine document to the verdict the demo draws. Strings pass through untouched. */
export function verdictFromDoc(doc: EngineDoc): DemoVerdict {
  if (doc.status === "refused") {
    return { kind: "refused", code: doc.error.code, message: doc.error.message, stopAt: stageForRefusal(doc.error.code) };
  }
  const txns = doc.data.transactions;
  const batch = doc.data.batches[0];
  return {
    kind: "released",
    currency: batch?.currency ?? "",
    opening: batch?.opening?.amount ?? "",
    closing: batch?.closing?.amount ?? "",
    rowCount: txns.length,
    rows: txns.slice(0, LEDGER_PREVIEW).map((t) => ({
      id: t.id,
      date: t.date ?? "",
      direction: t.direction === "credit" ? "CR" : t.direction === "debit" ? "DR" : "",
      description: t.description ?? "",
      amount: t.amount?.amount ?? "",
      balance: t.balance_after?.amount ?? "",
    })),
    hiddenRowCount: Math.max(0, txns.length - LEDGER_PREVIEW),
    checks: doc.assertions.map((a) => ({ id: a.id, rule: a.rule, passed: a.passed, independent: a.independent })),
  };
}

export type DemoReplay = { verdict: DemoVerdict; stagesReached: Stage[] };

/** Recorded real runs (proof-data.ts), replayed when the engine cannot be reached. */
export const REPLAYS: Record<DemoSampleId, DemoReplay> = {
  ok_bank_csv: {
    stagesReached: ["detect", "parse", "normalise", "balance"],
    verdict: {
      kind: "released",
      currency: RELEASED.currency,
      opening: RELEASED.opening,
      closing: RELEASED.closing,
      rowCount: RELEASED.transactionCount,
      rows: [...RELEASED.rows],
      hiddenRowCount: RELEASED.hiddenRowCount,
      checks: [
        {
          id: RELEASED.equationAssertion.id,
          rule: RELEASED.equationAssertion.rule,
          passed: RELEASED.equationAssertion.passed,
          independent: RELEASED.equationAssertion.independent,
        },
      ],
    },
  },
  bad_bank_balance_break: {
    stagesReached: ["detect", "parse", "normalise"],
    verdict: { kind: "refused", code: TAMPERED.code, message: TAMPERED.message, stopAt: "balance" },
  },
};
