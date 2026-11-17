import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import { SYSTEM_PROMPT } from "@/lib/server/ask-prompt";
import { buildDigest } from "@/lib/digest";
import { groupAmount } from "@/lib/ledger";
import { getEvidence, queryTransactions, type DocRef, type TxnFilter } from "@/lib/query";
import type { EngineDoc } from "@/lib/types";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MODEL = "claude-opus-5-5";
const MAX_TURNS = 8;

function hasCredentials(): boolean {
  return Boolean(process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN || process.env.ANTHROPIC_PROFILE);
}

/** Lets the composer know up front whether questions are available. */
export function GET() {
  return Response.json({ enabled: hasCredentials(), model: MODEL });
}

const Body = z.object({
  question: z.string().trim().min(1).max(4000),
  history: z.array(z.object({ role: z.enum(["user", "assistant"]), content: z.string().max(20000) })).max(40),
  docs: z
    .array(z.object({ file: z.string().max(300), doc: z.record(z.string(), z.unknown()) }))
    .max(200),
});

const Amount = z.string().regex(/^-?\d+(\.\d+)?$/, "plain decimal like 1000.00");
const IsoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "YYYY-MM-DD");

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

const TOOLS: Anthropic.Beta.BetaTool[] = [
  {
    name: "query_transactions",
    description:
      "Filter the released documents' transactions and get an exact count and per-currency decimal sum. Use this for every total, count or comparison of money; never compute amounts yourself. Refused files are skipped and listed in skipped_refused. Filters combine with AND. The amount used per row is: amount (bank and Wise statements), net (Stripe, Razorpay and PayPal settlements), inr_amount (FIRA), reported_value (AIS), gain_loss (Form 1099-B), or debit/credit (trial balance, debits negative). Set field to sum another money field instead, e.g. proceeds or cost_basis (1099-B), gross or fee (settlements), tax_deducted (26AS). min_amount/max_amount compare the absolute value of that amount. Rows are capped by limit but count and sums always cover every match.",
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
    eager_input_streaming: true,
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
    eager_input_streaming: true,
  },
];

type Out =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; summary: string }
  | { type: "error"; message: string }
  | { type: "done" };

function summarise(name: string, input: Record<string, unknown>, result: unknown): string {
  const args = Object.entries(input)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => (k === "description_contains" ? `desc~"${v}"` : `${k}=${v}`))
    .join(" · ");
  if (name === "query_transactions" && result && typeof result === "object" && "count" in result) {
    const r = result as ReturnType<typeof queryTransactions>;
    const sums = Object.entries(r.sums).map(([c, s]) => `${groupAmount(s, c)} ${c}`).join(", ");
    return `${args || "all files"} → ${r.count} row${r.count === 1 ? "" : "s"}${sums ? ` · ${sums}` : ""}`;
  }
  if (result && typeof result === "object" && "error" in result) return `${args} → ${(result as { error: string }).error}`;
  return `${args} → ${Object.keys(result as object).length} field${Object.keys(result as object).length === 1 ? "" : "s"}`;
}

function runTool(docs: DocRef[], block: Anthropic.Beta.BetaToolUseBlock): { content: string; isError: boolean; summary: string } {
  if (block.name === "query_transactions") {
    const p = QueryInput.safeParse(block.input);
    if (!p.success) return { content: `invalid input: ${p.error.message}`, isError: true, summary: "invalid query" };
    const r = queryTransactions(docs, p.data as TxnFilter);
    return { content: JSON.stringify(r), isError: false, summary: summarise(block.name, p.data, r) };
  }
  if (block.name === "get_evidence") {
    const p = EvidenceInput.safeParse(block.input);
    if (!p.success) return { content: `invalid input: ${p.error.message}`, isError: true, summary: "invalid evidence lookup" };
    const r = getEvidence(docs, p.data.file, p.data.record_id, p.data.field);
    return { content: JSON.stringify(r), isError: "error" in r, summary: summarise(block.name, p.data, r) };
  }
  return { content: `unknown tool ${block.name}`, isError: true, summary: `unknown tool ${block.name}` };
}

function errorMessage(err: unknown): string {
  if (err instanceof Anthropic.AuthenticationError) return "The Claude API key on the web server was rejected.";
  if (err instanceof Anthropic.PermissionDeniedError) return "The Claude API key on the web server lacks access to this model.";
  if (err instanceof Anthropic.RateLimitError) return "Claude is rate limited right now. Try again in a minute.";
  if (err instanceof Anthropic.BadRequestError) return `Claude rejected the request: ${err.message}`;
  if (err instanceof Anthropic.APIError && (err.status ?? 0) >= 500) return "Claude is temporarily unavailable. Try again shortly.";
  if (err instanceof Anthropic.APIConnectionError) return "Could not reach the Claude API from the web server.";
  return "Something went wrong while answering.";
}

export async function POST(req: Request) {
  if (!hasCredentials()) {
    return Response.json(
      { error: "ask_disabled", message: "Questions need ANTHROPIC_API_KEY on the web server. File runs still work." },
      { status: 503 },
    );
  }
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "bad_request", message: parsed.error.message }, { status: 400 });
  const { question, history } = parsed.data;
  const docs = parsed.data.docs as unknown as DocRef[] & { doc: EngineDoc }[];

  const client = new Anthropic();
  const messages: Anthropic.Beta.BetaMessageParam[] = [
    {
      role: "user",
      content: [{ type: "text", text: `<documents>\n${buildDigest(docs)}\n</documents>`, cache_control: { type: "ephemeral" } }],
    },
    ...history.map((h) => ({ role: h.role, content: h.content })),
    { role: "user", content: question },
  ];

  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (o: Out) => controller.enqueue(enc.encode(JSON.stringify(o) + "\n"));
      try {
        for (let turn = 0; turn < MAX_TURNS; turn++) {
          const stream = client.beta.messages.stream(
            {
              model: MODEL,
              max_tokens: 16000,
              system: [{ type: "text", text: SYSTEM_PROMPT, cache_control: { type: "ephemeral" } }],
              thinking: { type: "adaptive" },
              output_config: { effort: "medium" },
              betas: ["server-side-fallback-2026-07-01"],
              fallbacks: "default",
              tools: TOOLS,
              messages,
            },
            { signal: req.signal },
          );
          stream.on("text", (text) => send({ type: "text", text }));
          const message = await stream.finalMessage();

          if (message.stop_reason === "refusal") {
            send({ type: "error", message: "Claude declined to answer this question." });
            break;
          }
          const uses = message.content.filter((b): b is Anthropic.Beta.BetaToolUseBlock => b.type === "tool_use");
          if (uses.length === 0) break;
          if (message.stop_reason === "max_tokens") {
            send({ type: "error", message: "The answer was cut off before a lookup finished. Ask a narrower question." });
            break;
          }
          // Thinking and tool_use blocks go back unchanged, in order.
          messages.push({ role: "assistant", content: message.content as Anthropic.Beta.BetaContentBlockParam[] });
          const results: Anthropic.Beta.BetaToolResultBlockParam[] = uses.map((u) => {
            const r = runTool(docs, u);
            send({ type: "tool", name: u.name, summary: r.summary });
            return { type: "tool_result", tool_use_id: u.id, content: r.content, is_error: r.isError };
          });
          messages.push({ role: "user", content: results });
          if (turn === MAX_TURNS - 1) send({ type: "error", message: "Stopped after too many lookups. Ask a narrower question." });
        }
        send({ type: "done" });
      } catch (err) {
        if (!req.signal.aborted) {
          console.error("ask failed", err instanceof Anthropic.APIError ? { status: err.status, requestId: err.requestID } : err);
          send({ type: "error", message: errorMessage(err) });
          send({ type: "done" });
        }
      } finally {
        controller.close();
      }
    },
  });

  return new Response(body, { headers: { "content-type": "application/x-ndjson; charset=utf-8", "cache-control": "no-store" } });
}
