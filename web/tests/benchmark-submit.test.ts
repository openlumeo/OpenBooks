import { describe, expect, it } from "vitest";
import { createTokenBucket } from "@/lib/token-bucket";
import { handleBenchmarkSubmit, type SubmitDeps } from "@/lib/benchmark/submit";
import type { StoredSubmission } from "@/lib/benchmark/store";

const DIGEST = "a".repeat(64);
const URL_SUBMIT = "https://openbooks.example/api/benchmark/submit";

const taskSet = {
  label: "fixture-v1",
  taskIds: ["csv-balanced-01", "tamper-01"],
  expected: {
    "csv-balanced-01": {
      outcome: "released" as const,
      fields: { transaction_count: 2, closing_balance: "1299.50", currency: "INR" },
    },
    "tamper-01": { outcome: "refused" as const },
  },
};

const csvTask = {
  id: "csv-balanced-01",
  final_answer: "2 transactions, closing 1299.50 INR",
  tool_calls: 2,
  input_tokens: 1200,
  output_tokens: 300,
  elapsed_s: 8.4,
  engine_outcomes: [{
    layout: "bank_csv.v1",
    status: "released",
    refusal_code: null,
    fields: { transaction_count: 2, closing_balance: "1299.50", currency: "INR" },
  }],
  error: null,
};

const tamperTask = {
  id: "tamper-01",
  final_answer: "I cannot release these figures: the balance does not reconcile.",
  tool_calls: 2,
  input_tokens: 900,
  output_tokens: 120,
  elapsed_s: 5.1,
  engine_outcomes: [{ layout: "bank_csv.v1", status: "refused", refusal_code: "BALANCE_MISMATCH", fields: {} }],
  error: null,
};

function bundle(overrides: Record<string, unknown> = {}) {
  return {
    schema: "openbooks.bench.v1",
    kit_version: "0.2.4",
    run_id: crypto.randomUUID(),
    created_at: "2026-11-24T10:00:00Z",
    model: { provider: "anthropic", name: "claude-test-1" },
    tasks: [csvTask, tamperTask],
    tasks_digest: DIGEST,
    ...overrides,
  };
}

function submit(body: unknown, deps: SubmitDeps) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return handleBenchmarkSubmit(
    new Request(URL_SUBMIT, { method: "POST", headers: { "content-type": "application/json" }, body: text }),
    deps,
  );
}

function fixtureDeps(overrides: Partial<SubmitDeps> = {}) {
  const inserted: StoredSubmission[] = [];
  const runIds = new Set<string>();
  const deps: SubmitDeps = {
    rateLimit: async () => null,
    store: {
      insert: async (record) => {
        if (runIds.has(record.runId)) return null;
        runIds.add(record.runId);
        inserted.push(record);
        return { id: crypto.randomUUID() };
      },
    },
    taskSets: { [DIGEST]: taskSet },
    ...overrides,
  };
  return { deps, inserted };
}

describe("handleBenchmarkSubmit validation", () => {
  it("stores server-computed scores, ignores claimed scores, and keeps no answer text", async () => {
    const { deps, inserted } = fixtureDeps();
    const response = await submit(bundle({ scores: { overall: 0.01, release_accuracy: 0 } }), deps);
    expect(response.status).toBe(201);
    const body = await response.json();
    expect(body.task_set).toBe("fixture-v1");
    expect(body.scores.overall).toBe(1);
    expect(body.scores.release_accuracy).toBe(1);
    expect(inserted).toHaveLength(1);
    expect(inserted[0]?.scores.overall).toBe(1);
    expect(inserted[0]?.provider).toBe("anthropic");
    expect(inserted[0]?.modelName).toBe("claude-test-1");
    expect(JSON.stringify(inserted)).not.toContain("2 transactions, closing");
    expect(JSON.stringify(inserted)).not.toContain("does not reconcile");
  });

  it("rejects an oversize body before it is parsed or stored", async () => {
    const { deps, inserted } = fixtureDeps();
    const response = await submit(bundle({ padding: "a".repeat(300_000) }), deps);
    expect(response.status).toBe(413);
    expect(inserted).toHaveLength(0);
  });

  it("rejects a wrong schema", async () => {
    const { deps, inserted } = fixtureDeps();
    const response = await submit(bundle({ schema: "openbooks.bench.v2" }), deps);
    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("unsupported_schema");
    expect(inserted).toHaveLength(0);
  });

  it("rejects an unknown tasks_digest", async () => {
    const { deps, inserted } = fixtureDeps();
    const response = await submit(bundle({ tasks_digest: "b".repeat(64) }), deps);
    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("unknown_task_set");
    expect(inserted).toHaveLength(0);
  });

  it("rejects a malformed tasks_digest", async () => {
    const { deps } = fixtureDeps();
    expect((await submit(bundle({ tasks_digest: "not-a-digest" }), deps)).status).toBe(400);
  });

  it("rejects a bundle that omits tasks from its task set", async () => {
    const { deps, inserted } = fixtureDeps();
    const response = await submit(bundle({ tasks: [csvTask] }), deps);
    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("task_set_mismatch");
    expect(inserted).toHaveLength(0);
  });

  it("rejects a task id outside the task set", async () => {
    const { deps } = fixtureDeps();
    const response = await submit(bundle({ tasks: [csvTask, { ...tamperTask, id: "other-01" }] }), deps);
    expect(response.status).toBe(400);
  });

  it.each([
    ["an OpenAI-style key", "sk-proj-abcdefghijklmnop1234"],
    ["a Google key", "AIzaSyD-abcdefghijklmnopqrstuvwxyz123"],
    ["an xAI key", "xai-abcdefghijklmnop1234"],
    ["a bearer token", "Authorization: Bearer abcdefghijklmnop1234"],
    ["a long base64-like token", "QWxhZGRpbjpvcGVuIHNlc2FtZQQWxhZGRpbjpvcGVu"],
  ])("rejects a final_answer containing %s", async (_label, secret) => {
    const { deps, inserted } = fixtureDeps();
    const leaking = { ...csvTask, final_answer: `Here is the value ${secret}` };
    const response = await submit(bundle({ tasks: [leaking, tamperTask] }), deps);
    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("secret_like_content");
    expect(inserted).toHaveLength(0);
  });

  it("does not flag an ordinary hyphenated word as a key", async () => {
    const { deps } = fixtureDeps();
    const ordinary = { ...csvTask, final_answer: "risk-based-accounting closing 1299.50 INR, 2 transactions" };
    expect((await submit(bundle({ tasks: [ordinary, tamperTask] }), deps)).status).toBe(201);
  });

  it("rejects non-JSON bodies", async () => {
    const { deps } = fixtureDeps();
    const response = await submit("{not json", deps);
    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("invalid_json");
  });

  it("rejects a run_id that was already submitted with 409", async () => {
    const { deps, inserted } = fixtureDeps();
    const body = bundle();
    expect((await submit(body, deps)).status).toBe(201);
    const second = await submit(body, deps);
    expect(second.status).toBe(409);
    expect((await second.json()).error).toBe("duplicate_run");
    expect(inserted).toHaveLength(1);
  });

  it("answers 503 when the store fails rather than leaking the error", async () => {
    const { deps } = fixtureDeps({
      store: { insert: async () => { throw new Error("connection string postgres://secret"); } },
    });
    const response = await submit(bundle(), deps);
    expect(response.status).toBe(503);
    expect(JSON.stringify(await response.json())).not.toContain("postgres://");
  });

  it("returns the rate limiter's 429 and never reaches the store", async () => {
    const bucket = createTokenBucket({ capacity: 1, refillPerSec: 1 / 60, now: () => 0 });
    const { deps, inserted } = fixtureDeps({
      rateLimit: async () => {
        const verdict = bucket.take("203.0.113.9");
        return verdict.allowed ? null : Response.json({ error: "rate_limited" }, { status: 429 });
      },
    });
    expect((await submit(bundle(), deps)).status).toBe(201);
    const limited = await submit(bundle(), deps);
    expect(limited.status).toBe(429);
    expect(inserted).toHaveLength(1);
  });
});
