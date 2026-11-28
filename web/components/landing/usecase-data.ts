import type { RefusalCode } from "@/lib/types";
import { RELEASED, TAMPERED } from "./proof-data";

export type UseCase = {
  id: string;
  title: string;
  outcome: string;
  /** input -> output, shown in mono on the tile */
  io: string;
  /** interfaces that exist today (README, docs) */
  via: string[];
  file: string;
  /** one short caption per engine stage: Detect, Parse, Normalise, Balance */
  captions: [string, string, string, string];
  result:
    | { kind: "released"; json: [string, string, string] }
    | { kind: "refused"; code: RefusalCode; meaning: string; detail: string };
  span: 7 | 5 | 4;
};

export const USE_CASES: UseCase[] = [
  {
    id: "bank",
    title: "Import bank statements into a ledger",
    outcome: "A bank CSV or PDF in, one released JSON of transactions out, ready to post.",
    io: "statement.csv → openbooks.v1 · RELEASED",
    via: ["CLI", "Python", "Node", "HTTP"],
    file: RELEASED.fileName,
    captions: [
      "bank_csv.v1",
      `${RELEASED.transactionCount} rows read`,
      `${RELEASED.currency}, ISO dates`,
      `${RELEASED.opening} + ${RELEASED.creditTotal} − ${RELEASED.debitTotal} = ${RELEASED.closing}`,
    ],
    result: {
      kind: "released",
      json: [
        '"status": "ok",',
        `"closing": "${RELEASED.closing}",`,
        '"passed": true',
      ],
    },
    span: 7,
  },
  {
    id: "payouts",
    title: "Reconcile gateway payouts",
    outcome: "Gross minus fees and tax equals net on every row, then match the payout to its bank credit.",
    io: "razorpay-settlement.csv → openbooks.v1 · RELEASED",
    via: ["Node", "Python"],
    file: "razorpay-settlement.csv",
    captions: ["razorpay_settlement.v1", "settlement rows read", "INR decimals, no rounding", "gross − fee − tax = net, payout ties"],
    result: {
      kind: "released",
      json: [
        '"status": "ok",',
        '"layout_version": "razorpay_settlement.v1",',
        '"passed": true',
      ],
    },
    span: 5,
  },
  {
    id: "tds",
    title: "Pull TDS credits from Form 26AS",
    outcome: "Tax deducted and deposited, checked against the statement's own printed totals.",
    io: "form-26as.csv → openbooks.v1 · RELEASED",
    via: ["CLI", "Python", "Node"],
    file: "form-26as.csv",
    captions: ["tds_26as.v1", "deductor rows read", "amounts and dates typed", "rows match printed totals"],
    result: {
      kind: "released",
      json: [
        '"status": "ok",',
        '"layout_version": "tds_26as.v1",',
        '"passed": true',
      ],
    },
    span: 4,
  },
  {
    id: "agent",
    title: "Give an agent verified figures",
    outcome: "The MCP server lets an AI client check a file and read the proof before it answers.",
    io: "agent → openbooks-mcp → proof · RELEASED",
    via: ["MCP"],
    file: "statement.csv via MCP",
    captions: [
      "bank_csv.v1",
      `${RELEASED.transactionCount} rows read`,
      `${RELEASED.currency}, ISO dates`,
      "assertions returned with the data",
    ],
    result: {
      kind: "released",
      json: [
        '"status": "ok",',
        '"rule": "opening + sum(txns) = closing",',
        '"passed": true',
      ],
    },
    span: 4,
  },
  {
    id: "tamper",
    title: "Reject a tampered file",
    outcome: "Change one printed balance and the file is refused. Nothing partial is released.",
    io: "statement-tampered.csv → BALANCE_MISMATCH · REFUSED",
    via: ["CLI", "Python", "Node", "HTTP"],
    file: TAMPERED.fileName,
    captions: [
      "bank_csv.v1",
      "rows read",
      "decimals, ISO dates",
      `${TAMPERED.offendingRowId} prints ${TAMPERED.offendingPrintedBalance}, computes ${TAMPERED.offendingComputedBalance}`,
    ],
    result: {
      kind: "refused",
      code: "BALANCE_MISMATCH",
      meaning: "The file's own numbers do not tie out.",
      detail: "Stopped at Balance",
    },
    span: 4,
  },
];
