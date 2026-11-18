import OpenAI from "openai";
import { z } from "zod";
import { createRateLimiter, MAX_JSON_BYTES, rejectOversize } from "@/lib/guards";
import { SYSTEM_PROMPT } from "@/lib/server/ask-prompt";
import { buildDigest } from "@/lib/digest";
import { groupAmount } from "@/lib/ledger";
import { getEvidence, queryTransactions, type DocRef, type TxnFilter } from "@/lib/query";
import type { EngineDoc } from "@/lib/types";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MODEL = process.env.OPENBOOKS_LLM_MODEL ?? "";
const BASE_URL = process.env.OPENBOOKS_LLM_BASE_URL ?? "https://openrouter.ai/api/v1";
const MAX_TURNS = 8;
const MAX_TOKENS = 3000;
const askLimited = createRateLimiter(30, 60_000);

function hasCredentials(): boolean {
  return Boolean(MODEL && process.env.OPENBOOKS_LLM_API_KEY);
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

type ToolDef = { name: string; description: string; input_schema: Record<string, unknown> };

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

const TOOLS_OAI: OpenAI.Chat.ChatCompletionTool[] = TOOLS.map((t) => ({
  type: "function",
  function: { name: t.name, description: t.description, parameters: t.input_schema },
}));

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

function runTool(docs: DocRef[], block: { name: string; input: unknown }): { content: string; isError: boolean; summary: string } {
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
  if (err instanceof OpenAI.AuthenticationError) return "The model API key on the web server was rejected.";
  if (err instanceof OpenAI.PermissionDeniedError) return "The model API key on the web server lacks access to this model.";
  if (err instanceof OpenAI.RateLimitError) return "The model is rate limited right now. Try again in a minute.";
  if (err instanceof OpenAI.BadRequestError) return `The model rejected the request: ${err.message}`;
  if (err instanceof OpenAI.APIError && (err.status ?? 0) >= 500) return "The model is temporarily unavailable. Try again shortly.";
  if (err instanceof OpenAI.APIConnectionError) return "Could not reach the model API from the web server.";
  return "Something went wrong while answering.";
}

export async function POST(req: Request) {
  if (!hasCredentials()) {
    return Response.json(
      { error: "ask_disabled", message: "Questions need OPENBOOKS_LLM_API_KEY and OPENBOOKS_LLM_MODEL on the web server. File runs still work." },
      { status: 503 },
    );
  }
  const tooBig = rejectOversize(req, MAX_JSON_BYTES);
  if (tooBig) return tooBig;
  if (askLimited()) {
    return Response.json({ error: "rate_limited", message: "Too many questions in the last minute. Try again shortly." }, { status: 429 });
  }
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "bad_request", message: parsed.error.message }, { status: 400 });
  const { question, history } = parsed.data;
  const docs = parsed.data.docs as unknown as DocRef[] & { doc: EngineDoc }[];

  const client = new OpenAI({ baseURL: BASE_URL, apiKey: process.env.OPENBOOKS_LLM_API_KEY });
  const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: `<documents>\n${buildDigest(docs)}\n</documents>` },
    ...history.map((h) => ({ role: h.role, content: h.content })),
    { role: "user", content: question },
  ];

  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (o: Out) => controller.enqueue(enc.encode(JSON.stringify(o) + "\n"));
      try {
        for (let turn = 0; turn < MAX_TURNS; turn++) {
          const stream = await client.chat.completions.create(
            {
              model: MODEL,
              max_tokens: MAX_TOKENS,
              temperature: 0,
              stream: true,
              tools: TOOLS_OAI,
              messages,
              provider: { sort: "latency", require_parameters: true },
            } as OpenAI.Chat.ChatCompletionCreateParamsStreaming,
            { signal: req.signal },
          );
          let text = "";
          let finish: string | null = null;
          const calls: { id: string; name: string; args: string }[] = [];
          for await (const chunk of stream) {
            const choice = chunk.choices[0];
            if (!choice) continue;
            if (choice.delta.content) {
              text += choice.delta.content;
              send({ type: "text", text: choice.delta.content });
            }
            for (const tc of choice.delta.tool_calls ?? []) {
              const c = (calls[tc.index] ??= { id: "", name: "", args: "" });
              if (tc.id) c.id = tc.id;
              if (tc.function?.name) c.name += tc.function.name;
              if (tc.function?.arguments) c.args += tc.function.arguments;
            }
            if (choice.finish_reason) finish = choice.finish_reason;
          }

          const uses = calls.filter(Boolean).map((c, i) => ({ ...c, id: c.id || `call_${turn}_${i}` }));
          if (uses.length === 0) break;
          if (finish === "length") {
            send({ type: "error", message: "The answer was cut off before a lookup finished. Ask a narrower question." });
            break;
          }
          messages.push({
            role: "assistant",
            content: text || null,
            tool_calls: uses.map((u) => ({ id: u.id, type: "function" as const, function: { name: u.name, arguments: u.args } })),
          });
          for (const u of uses) {
            let input: unknown = null;
            try {
              input = JSON.parse(u.args || "{}");
            } catch {
              input = null;
            }
            const r =
              input === null
                ? { content: "invalid input: arguments were not valid JSON", summary: "invalid query" }
                : runTool(docs, { name: u.name, input });
            send({ type: "tool", name: u.name, summary: r.summary });
            messages.push({ role: "tool", tool_call_id: u.id, content: r.content });
          }
          if (turn === MAX_TURNS - 1) send({ type: "error", message: "Stopped after too many lookups. Ask a narrower question." });
        }
        send({ type: "done" });
      } catch (err) {
        if (!req.signal.aborted) {
          console.error("ask failed", err instanceof OpenAI.APIError ? { status: err.status } : err);
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
