import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const limiter = vi.hoisted(() => ({ limitOr429: vi.fn() }));
vi.mock("@/lib/server/limiter", () => limiter);
const db = vi.hoisted(() => ({ sql: vi.fn() }));
vi.mock("@neondatabase/serverless", () => ({ neon: () => db.sql }));
const llm = vi.hoisted(() => ({ create: vi.fn() }));
vi.mock("openai", () => ({
  default: class {
    chat = { completions: { create: llm.create } };
    constructor(_options: unknown) {}
  },
}));

import { POST as subscribePost } from "@/app/api/subscribe/route";

function subscribe(body: string, headers: Record<string, string> = { "content-type": "application/json" }): Request {
  return new Request("http://localhost/api/subscribe", { method: "POST", headers, body });
}

beforeEach(() => {
  limiter.limitOr429.mockReset();
  limiter.limitOr429.mockResolvedValue(null);
  db.sql.mockReset();
  db.sql.mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("POST /api/subscribe", () => {
  it("answers 429 when the limiter refuses the caller", async () => {
    limiter.limitOr429.mockResolvedValueOnce(Response.json({ error: "rate_limited" }, { status: 429 }));
    expect((await subscribePost(subscribe('{"email":"a@b.co"}'))).status).toBe(429);
  });

  it("answers 415 when the body is not JSON", async () => {
    const res = await subscribePost(subscribe("a@b.co", { "content-type": "text/plain" }));
    expect(res.status).toBe(415);
    expect(await res.json()).toEqual({ error: "unsupported_media_type", message: "Send application/json." });
  });

  it("answers 413 when the body exceeds 2 KB", async () => {
    const res = await subscribePost(subscribe(JSON.stringify({ email: "a@b.co", pad: "x".repeat(2100) })));
    expect(res.status).toBe(413);
  });

  it("answers 400 when the body is not valid JSON", async () => {
    expect((await subscribePost(subscribe("{nope"))).status).toBe(400);
  });

  it("answers 422 for an invalid email", async () => {
    const res = await subscribePost(subscribe('{"email":"not-an-email"}'));
    expect(res.status).toBe(422);
    expect(db.sql).not.toHaveBeenCalled();
  });

  it("pretends success for a filled honeypot field without storing anything", async () => {
    const res = await subscribePost(subscribe('{"email":"a@b.co","website":"https://spam.example"}'));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
    expect(db.sql).not.toHaveBeenCalled();
  });

  it("answers 503 when the database write fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    db.sql.mockRejectedValueOnce(new Error("connection reset"));
    const res = await subscribePost(subscribe('{"email":"a@b.co"}'));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ error: "unavailable" });
  });

  it("stores the normalised email and answers 200 for a valid request", async () => {
    const res = await subscribePost(subscribe('{"email":"  Ada@Example.COM "}'));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
    expect(db.sql.mock.calls[0]).toContain("ada@example.com");
  });
});

describe("POST /api/ask", () => {
  async function loadAsk(env: Record<string, string>) {
    vi.resetModules();
    for (const [key, value] of Object.entries(env)) vi.stubEnv(key, value);
    return import("@/app/api/ask/route");
  }

  function question(body: string, contentLength?: string): Request {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (contentLength !== undefined) headers["content-length"] = contentLength;
    return new Request("http://localhost/api/ask", { method: "POST", headers, body });
  }

  const enabled = { OPENBOOKS_LLM_API_KEY: "key", OPENBOOKS_LLM_MODEL: "test-model" };
  const validBody = JSON.stringify({ question: "What is the total?", history: [], docs: [] });

  beforeEach(() => {
    llm.create.mockReset();
  });

  it("reports whether questions are enabled", async () => {
    const route = await loadAsk({ OPENBOOKS_LLM_API_KEY: "", OPENBOOKS_LLM_MODEL: "test-model" });
    expect(await route.GET().json()).toEqual({ enabled: false, model: "test-model" });
    const enabledRoute = await loadAsk(enabled);
    expect(await enabledRoute.GET().json()).toEqual({ enabled: true, model: "test-model" });
  });

  it("answers 503 ask_disabled when the model key is missing", async () => {
    const route = await loadAsk({ OPENBOOKS_LLM_API_KEY: "", OPENBOOKS_LLM_MODEL: "test-model" });
    const res = await route.POST(question(validBody, String(validBody.length)));
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ error: "ask_disabled" });
    expect(llm.create).not.toHaveBeenCalled();
  });

  it("answers 413 above the 4 MB JSON cap", async () => {
    const route = await loadAsk(enabled);
    expect((await route.POST(question(validBody, String(4 * 1024 * 1024 + 1)))).status).toBe(413);
  });

  it("answers 429 when the limiter refuses the caller", async () => {
    const route = await loadAsk(enabled);
    limiter.limitOr429.mockResolvedValueOnce(Response.json({ error: "rate_limited" }, { status: 429 }));
    expect((await route.POST(question(validBody, String(validBody.length)))).status).toBe(429);
  });

  it("answers 400 when the body fails validation", async () => {
    const route = await loadAsk(enabled);
    limiter.limitOr429.mockResolvedValue(null);
    const res = await route.POST(question("{}", "2"));
    expect(res.status).toBe(400);
    expect(await res.json()).toMatchObject({ error: "bad_request" });
  });

  it("streams a plain answer as text events followed by done", async () => {
    const route = await loadAsk(enabled);
    limiter.limitOr429.mockResolvedValue(null);
    llm.create.mockResolvedValueOnce(
      (async function* () {
        yield { choices: [{ delta: { content: "Total is 5" }, finish_reason: "stop" }] };
      })(),
    );
    const res = await route.POST(question(validBody, String(validBody.length)));
    expect(res.headers.get("content-type")).toContain("application/x-ndjson");
    const lines = (await res.text()).trim().split("\n").map((line) => JSON.parse(line) as unknown);
    expect(lines).toEqual([
      { type: "text", text: "Total is 5" },
      { type: "done" },
    ]);
  });

  it("answers a tool lookup and then continues with the model's final text", async () => {
    const route = await loadAsk(enabled);
    limiter.limitOr429.mockResolvedValue(null);
    llm.create
      .mockResolvedValueOnce(
        (async function* () {
          yield {
            choices: [
              {
                delta: {
                  tool_calls: [{ index: 0, id: "call-1", function: { name: "query_transactions", arguments: '{"direction":"credit"}' } }],
                },
                finish_reason: "tool_calls",
              },
            ],
          };
        })(),
      )
      .mockResolvedValueOnce(
        (async function* () {
          yield { choices: [{ delta: { content: "None found." }, finish_reason: "stop" }] };
        })(),
      );
    const res = await route.POST(question(validBody, String(validBody.length)));
    const events = (await res.text()).trim().split("\n").map((line) => JSON.parse(line) as { type: string; name?: string });
    expect(events.map((e) => e.type)).toEqual(["tool", "text", "done"]);
    expect(events[0]?.name).toBe("query_transactions");
    expect(llm.create).toHaveBeenCalledTimes(2);
  });
});
