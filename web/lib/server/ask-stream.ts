import OpenAI from "openai";
import type { DocRef } from "@/lib/query";
import { runTool, TOOLS_OAI, type ToolOutcome } from "@/lib/server/ask-tools";

const MAX_TURNS = 8;
const MAX_TOKENS = 3000;

type Out =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; summary: string }
  | { type: "error"; message: string }
  | { type: "done" };

type Send = (out: Out) => void;
type Messages = OpenAI.Chat.ChatCompletionMessageParam[];
type ToolCall = { id: string; name: string; args: string };
type Turn = { text: string; finish: string | null; calls: ToolCall[] };

function errorMessage(err: unknown): string {
  if (err instanceof OpenAI.AuthenticationError) return "The model API key on the web server was rejected.";
  if (err instanceof OpenAI.PermissionDeniedError) return "The model API key on the web server lacks access to this model.";
  if (err instanceof OpenAI.RateLimitError) return "The model is rate limited right now. Try again in a minute.";
  if (err instanceof OpenAI.BadRequestError) return "The model rejected this question. Try a shorter request.";
  if (err instanceof OpenAI.APIError && (err.status ?? 0) >= 500) return "The model is temporarily unavailable. Try again shortly.";
  if (err instanceof OpenAI.APIConnectionError) return "Could not reach the model API from the web server.";
  return "Something went wrong while answering.";
}

async function readTurn(stream: AsyncIterable<OpenAI.Chat.ChatCompletionChunk>, send: Send): Promise<Turn> {
  let text = "";
  let finish: string | null = null;
  const calls: ToolCall[] = [];
  for await (const chunk of stream) {
    const choice = chunk.choices[0];
    if (!choice) continue;
    if (choice.delta.content) {
      text += choice.delta.content;
      send({ type: "text", text: choice.delta.content });
    }
    for (const tc of choice.delta.tool_calls ?? []) {
      const call = (calls[tc.index] ??= { id: "", name: "", args: "" });
      if (tc.id) call.id = tc.id;
      if (tc.function?.name) call.name += tc.function.name;
      if (tc.function?.arguments) call.args += tc.function.arguments;
    }
    if (choice.finish_reason) finish = choice.finish_reason;
  }
  return { text, finish, calls };
}

function runCall(docs: DocRef[], call: ToolCall, messages: Messages, send: Send): void {
  let input: unknown = null;
  try {
    input = JSON.parse(call.args || "{}");
  } catch {
    input = null;
  }
  const outcome: ToolOutcome =
    input === null
      ? { content: "invalid input: arguments were not valid JSON", isError: true, summary: "invalid query" }
      : runTool(docs, call.name, input);
  send({ type: "tool", name: call.name, summary: outcome.summary });
  messages.push({ role: "tool", tool_call_id: call.id, content: outcome.content });
}

async function runTurns(
  client: OpenAI,
  model: string,
  messages: Messages,
  docs: DocRef[],
  signal: AbortSignal,
  send: Send,
): Promise<void> {
  for (let turn = 0; turn < MAX_TURNS; turn++) {
    const stream = await client.chat.completions.create(
      {
        model,
        max_tokens: MAX_TOKENS,
        temperature: 0,
        stream: true,
        tools: TOOLS_OAI,
        messages,
        provider: { sort: "latency", require_parameters: true },
      } as OpenAI.Chat.ChatCompletionCreateParamsStreaming,
      { signal },
    );
    const { text, finish, calls } = await readTurn(stream, send);
    const uses = calls.filter(Boolean).map((c, i) => ({ ...c, id: c.id || `call_${turn}_${i}` }));
    if (uses.length === 0) return;
    if (finish === "length") {
      send({ type: "error", message: "The answer was cut off before a lookup finished. Ask a narrower question." });
      return;
    }
    messages.push({
      role: "assistant",
      content: text || null,
      tool_calls: uses.map((u) => ({ id: u.id, type: "function" as const, function: { name: u.name, arguments: u.args } })),
    });
    for (const u of uses) runCall(docs, u, messages, send);
    if (turn === MAX_TURNS - 1) send({ type: "error", message: "Stopped after too many lookups. Ask a narrower question." });
  }
}

export function answerStream(
  client: OpenAI,
  model: string,
  messages: Messages,
  docs: DocRef[],
  signal: AbortSignal,
): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const send: Send = (o) => controller.enqueue(enc.encode(JSON.stringify(o) + "\n"));
      try {
        await runTurns(client, model, messages, docs, signal, send);
        send({ type: "done" });
      } catch (err) {
        if (!signal.aborted) {
          console.error("ask failed", err instanceof OpenAI.APIError ? { status: err.status } : err);
          send({ type: "error", message: errorMessage(err) });
          send({ type: "done" });
        }
      } finally {
        controller.close();
      }
    },
  });
}
