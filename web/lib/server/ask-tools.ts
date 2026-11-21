import OpenAI from "openai";
import { z } from "zod";
import { groupAmount } from "@/lib/ledger";
import { getEvidence, queryTransactions, type DocRef } from "@/lib/query";
import { Amount, IsoDate } from "@/lib/server/ask-input";

type ToolDef = { name: string; description: string; input_schema: Record<string, unknown> };

const QueryInput = z
  .object({
    file: z.string().optional(),
    direction: z.enum(["credit", "debit"]).optional(),
    kind: z.string().optional(),
    description_contains: z.string().optional(),
    date_from: IsoDate.optional(),
    date_to: IsoDate.optional(),
    min_amount: Amount.optional(),
    max_amount: Amount.optional(),
    field: z.string().regex(/^[a-z_]{1,40}$/).optional(),
    limit: z.number().int().min(1).max(200).optional(),
  })
  .strict();

const EvidenceInput = z.object({ file: z.string(), record_id: z.string(), field: z.string().optional() }).strict();

const TOOLS: ToolDef[] = [
  {
    name: "query_transactions",
    description:
      "Filter the released documents' transactions and get an exact count and per-currency decimal sum. Use this for every total, count or comparison of money; never compute amounts yourself. Refused files are skipped and listed in skipped_refused. Filters combine with AND. The amount used per row is: amount (bank and Wise statements), net (Stripe, Razorpay and PayPal settlements), inr_amount (FIRA), reported_value (AIS), gain_loss (Form 1099-B), or debit/credit (trial balance, debits negative). Set field to sum another money field instead, e.g. proceeds or cost_basis (1099-B), gross or fee (settlements), tax_deducted (26AS). min_amount/max_amount compare the absolute value of that amount. Rows are capped by limit but count and sums always cover every match. The result also has by_direction: the count and per-currency sums for credit and debit separately. Read credit and debit totals from by_direction; never split rows or add amounts yourself.",
    input_schema: {
      type: "object",
      properties: {
        file: { type: "string", description: "Exact file key from <documents>. Omit to search all released files." },
        direction: { type: "string", enum: ["credit", "debit"], description: "Statements only: money in (credit) or out (debit)." },
        kind: { type: "string", description: "Row kind, e.g. charge, refund, payment, tds, fira, ais, 1099b, ledger_balance." },
        description_contains: { type: "string", description: "Case-insensitive match on description, reference, kind, deductor, remitter, account or category." },
        date_from: { type: "string", description: "Inclusive, YYYY-MM-DD." },
        date_to: { type: "string", description: "Inclusive, YYYY-MM-DD." },
        min_amount: { type: "string", description: "Plain decimal, compared to the absolute row amount." },
        max_amount: { type: "string", description: "Plain decimal, compared to the absolute row amount." },
        field: { type: "string", description: "Money field to sum instead of the default row amount, e.g. proceeds, cost_basis, fee, gross, tax_deducted." },
        limit: { type: "integer", description: "Rows to return, 1-200. Default 50." },
      },
      additionalProperties: false,
    },
  },
  {
    name: "get_evidence",
    description:
      "Where a released value came from: page, bounding box, row, the raw text exactly as printed, and the extraction method (parser, pdf_text, ocr, optionally +model). Record ids look like txn-00004 or batch-1. Omit field to get every field of the record.",
    input_schema: {
      type: "object",
      properties: {
        file: { type: "string", description: "Exact file key from <documents>." },
        record_id: { type: "string" },
        field: { type: "string", description: "e.g. amount, balance_after, date, opening, closing, net." },
      },
      required: ["file", "record_id"],
      additionalProperties: false,
    },
  },
];

export const TOOLS_OAI: OpenAI.Chat.ChatCompletionTool[] = TOOLS.map((t) => ({
  type: "function",
  function: { name: t.name, description: t.description, parameters: t.input_schema },
}));

function pluralRows(count: number): string {
  return `${count} row${count === 1 ? "" : "s"}`;
}

function pluralFields(count: number): string {
  return `${count} field${count === 1 ? "" : "s"}`;
}

function formatArgs(input: Record<string, unknown>): string {
  return Object.entries(input)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => (k === "description_contains" ? `desc~"${v}"` : `${k}=${v}`))
    .join(" · ");
}

function summarise(name: string, input: Record<string, unknown>, result: unknown): string {
  const args = formatArgs(input);
  if (name === "query_transactions" && result && typeof result === "object" && "count" in result) {
    const r = result as ReturnType<typeof queryTransactions>;
    const sums = Object.entries(r.sums).map(([c, s]) => `${groupAmount(s, c)} ${c}`).join(", ");
    return `${args || "all files"} → ${pluralRows(r.count)}${sums ? ` · ${sums}` : ""}`;
  }
  if (result && typeof result === "object" && "error" in result) return `${args} → ${(result as { error: string }).error}`;
  return `${args} → ${pluralFields(Object.keys(result as object).length)}`;
}

export type ToolOutcome = { content: string; isError: boolean; summary: string };

function runQueryTool(docs: DocRef[], input: unknown): ToolOutcome {
  const p = QueryInput.safeParse(input);
  if (!p.success) return { content: `invalid input: ${p.error.message}`, isError: true, summary: "invalid query" };
  const r = queryTransactions(docs, p.data);
  return { content: JSON.stringify(r), isError: false, summary: summarise("query_transactions", p.data, r) };
}

function runEvidenceTool(docs: DocRef[], input: unknown): ToolOutcome {
  const p = EvidenceInput.safeParse(input);
  if (!p.success) return { content: `invalid input: ${p.error.message}`, isError: true, summary: "invalid evidence lookup" };
  const r = getEvidence(docs, p.data.file, p.data.record_id, p.data.field);
  return { content: JSON.stringify(r), isError: "error" in r, summary: summarise("get_evidence", p.data, r) };
}

/** Runs one model-requested tool against the released documents. Unknown names and bad input come back as errors, never throws. */
export function runTool(docs: DocRef[], name: string, input: unknown): ToolOutcome {
  if (name === "query_transactions") return runQueryTool(docs, input);
  if (name === "get_evidence") return runEvidenceTool(docs, input);
  return { content: `unknown tool ${name}`, isError: true, summary: `unknown tool ${name}` };
}
