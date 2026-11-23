import OpenAI from "openai";
import type { DocRef } from "@/lib/query";
import { runTool, TOOLS_OAI, type ToolOutcome } from "@/lib/server/ask-tools";

const MAX_TURNS = 8;
const MAX_TOKENS = 3000;

type Out =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; summary: string }
  | { type: "error"; message: string }
  | { type: "done"; usage?: Usage };

type Send = (out: Out) => void;
type Messages = OpenAI.Chat.ChatCompletionMessageParam[];
type ToolCall = { id: string; name: string; args: string };
type Usage = { prompt_tokens: number; completion_tokens: number; total_tokens: number; reported_turns: number; turns: number };
type Turn = { text: string; finish: string | null; calls: ToolCall[]; usage?: OpenAI.CompletionUsage };

function errorMessage(err: unknown): string {
  if (err instanceof OpenAI.AuthenticationError) return "The model API key on the web server was rejected.";
  if (err instanceof OpenAI.PermissionDeniedError) return "The model API key on the web server lacks access to this model.";
  if (err instanceof OpenAI.RateLimitError) return "The model is rate limited right now. Try again in a minute.";
  if (err instanceof OpenAI.BadRequestError) return "The model rejected this question. Try a shorter request.";
  if (err instanceof OpenAI.APIError && (err.status ?? 0) >= 500) return "The model is temporarily unavailable. Try again shortly.";
  if (err instanceof OpenAI.APIConnectionError) return "Could not reach the model API from the web server.";
  return "Something went wrong while answering.";
}

async function readTurn(stream: AsyncIterable<OpenAI.Chat.ChatCompletionChunk>): Promise<Turn> {
  let text = "";
  let finish: string | null = null;
  const calls: ToolCall[] = [];
  let usage: OpenAI.CompletionUsage | undefined;
  for await (const chunk of stream) {
    if (chunk.usage) usage = chunk.usage;
    const choice = chunk.choices[0];
    if (!choice) continue;
    if (choice.delta.content) {
      text += choice.delta.content;
    }
    for (const tc of choice.delta.tool_calls ?? []) {
      const call = (calls[tc.index] ??= { id: "", name: "", args: "" });
      if (tc.id) call.id = tc.id;
      if (tc.function?.name) call.name += tc.function.name;
      if (tc.function?.arguments) call.args += tc.function.arguments;
    }
    if (choice.finish_reason) finish = choice.finish_reason;
  }
  return { text, finish, calls, usage };
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
  collectUsage: boolean,
  usage: Usage,
): Promise<void> {
  for (let turn = 0; turn < MAX_TURNS; turn++) {
    const stream = await client.chat.completions.create(
      {
        model,
        max_tokens: MAX_TOKENS,
        temperature: 0,
        stream: true,
        ...(collectUsage ? { stream_options: { include_usage: true } } : {}),
        tools: TOOLS_OAI,
        messages,
        provider: { sort: "latency", require_parameters: true },
      } as OpenAI.Chat.ChatCompletionCreateParamsStreaming,
      { signal },
    );
    usage.turns++;
    const { text, finish, calls, usage: turnUsage } = await readTurn(stream);
    if (turnUsage) {
      usage.reported_turns++;
      usage.prompt_tokens += turnUsage.prompt_tokens;
      usage.completion_tokens += turnUsage.completion_tokens;
      usage.total_tokens += turnUsage.total_tokens;
    }
    const uses = calls.filter(Boolean).map((c, i) => ({ ...c, id: c.id || `call_${turn}_${i}` }));
    if (finish === "length") {
      send({ type: "error", message: "The model ran out of space for this answer. Ask a narrower question." });
      return;
    }
    if (uses.length === 0) {
      if (finish === "stop" && text.trim()) send({ type: "text", text });
      else send({ type: "error", message: "The model did not complete an answer. Try again." });
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
  collectUsage = true,
): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  const cancellation = new AbortController();
  const requestSignal = AbortSignal.any([signal, cancellation.signal]);
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const send: Send = (o) => {
        if (!requestSignal.aborted) controller.enqueue(enc.encode(JSON.stringify(o) + "\n"));
      };
      const usage: Usage = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, reported_turns: 0, turns: 0 };
      try {
        await runTurns(client, model, messages, docs, requestSignal, send, collectUsage, usage);
      } catch (err) {
        if (!requestSignal.aborted) {
          console.error("ask failed", { status: err instanceof OpenAI.APIError ? err.status : undefined });
          send({ type: "error", message: errorMessage(err) });
        }
      } finally {
        if (usage.reported_turns) {
          console.info("openbooks.ask.usage", { model, ...usage });
        }
        send({ type: "done", ...(usage.reported_turns ? { usage } : {}) });
        if (!cancellation.signal.aborted) controller.close();
      }
    },
    cancel() {
      cancellation.abort();
    },
  });
}
