import OpenAI from "openai";
import { MAX_JSON_BYTES, rejectOversize } from "@/lib/guards";
import { jsonError } from "@/lib/http";
import { limitOr429 } from "@/lib/server/limiter";
import { AskBody } from "@/lib/server/ask-input";
import { answerStream } from "@/lib/server/ask-stream";
import { SYSTEM_PROMPT } from "@/lib/server/ask-prompt";
import { buildDigest } from "@/lib/digest";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MODEL = process.env.OPENBOOKS_LLM_MODEL ?? "";
const BASE_URL = process.env.OPENBOOKS_LLM_BASE_URL ?? "https://openrouter.ai/api/v1";

function hasCredentials(): boolean {
  return Boolean(MODEL && process.env.OPENBOOKS_LLM_API_KEY);
}

export function GET() {
  return Response.json({ enabled: hasCredentials(), model: MODEL });
}

export async function POST(req: Request) {
  if (!hasCredentials()) {
    return jsonError(
      503,
      "ask_disabled",
      "Questions need OPENBOOKS_LLM_API_KEY and OPENBOOKS_LLM_MODEL on the web server. File runs still work.",
    );
  }
  const tooBig = rejectOversize(req, MAX_JSON_BYTES);
  if (tooBig) return tooBig;
  const limited = await limitOr429(req, "ask");
  if (limited) return limited;
  const parsed = AskBody.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return jsonError(400, "bad_request", parsed.error.message);
  const { question, history, docs } = parsed.data;

  const client = new OpenAI({ baseURL: BASE_URL, apiKey: process.env.OPENBOOKS_LLM_API_KEY });
  const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: `<documents>\n${buildDigest(docs)}\n</documents>` },
    ...history.map((h) => ({ role: h.role, content: h.content })),
    { role: "user", content: question },
  ];

  const collectUsage = ["openrouter.ai", "api.openai.com"].includes(new URL(BASE_URL).hostname);
  return new Response(answerStream(client, MODEL, messages, docs, req.signal, collectUsage), {
    headers: { "content-type": "application/x-ndjson; charset=utf-8", "cache-control": "no-store" },
  });
}
