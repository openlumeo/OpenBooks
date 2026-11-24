import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";
import { describe, expect, it } from "vitest";
import { createBenchmarkStore, type StoredSubmission } from "@/lib/benchmark/store";

function scores(overall: number) {
  return {
    release_accuracy: overall,
    field_accuracy: overall,
    efficiency: overall,
    safety: overall,
    overall,
    critical_errors: [],
    per_task: {},
  };
}

function submission(overrides: Partial<StoredSubmission>): StoredSubmission {
  return {
    runId: crypto.randomUUID(),
    provider: "anthropic",
    modelName: "claude-a",
    taskSet: "fixture-v1",
    tasksDigest: "a".repeat(64),
    kitVersion: "0.2.4",
    scores: scores(0.5),
    engineOutcomes: [{ id: "csv-balanced-01", engine_outcomes: [{ status: "released", fields: { closing_balance: "1299.50" } }] }],
    ...overrides,
  };
}

async function openStore() {
  const db = new PGlite();
  const migration = await readFile(new URL("../migrations/003_benchmark_submissions.sql", import.meta.url), "utf8");
  await db.exec(migration);
  const store = createBenchmarkStore(async (text, params) => (await db.query<Record<string, unknown>>(text, params)).rows);
  return { db, store };
}

describe("benchmark leaderboard on isolated PostgreSQL", () => {
  it("keeps the best run per provider and model, sorted by overall, without audit data", async () => {
    const { db, store } = await openStore();
    try {
      await store.insert(submission({ modelName: "claude-a", scores: scores(0.6) }));
      await store.insert(submission({ modelName: "claude-a", scores: scores(0.9) }));
      await store.insert(submission({ provider: "openai", modelName: "gpt-b", scores: scores(0.8) }));
      await store.insert(submission({ provider: "compat", modelName: "local-x", scores: scores(0.95) }));

      const board = await store.leaderboard();
      expect(board.map((entry) => [entry.provider, entry.model, entry.overall])).toEqual([
        ["compat", "local-x", 0.95],
        ["anthropic", "claude-a", 0.9],
        ["openai", "gpt-b", 0.8],
      ]);
      expect(board[0]?.taskSet).toBe("fixture-v1");
      expect(JSON.stringify(board)).not.toContain("engine");
      expect(JSON.stringify(board)).not.toContain("1299.50");
    } finally {
      await db.close();
    }
  });

  it("returns null for a duplicate run_id instead of inserting twice", async () => {
    const { db, store } = await openStore();
    try {
      const runId = crypto.randomUUID();
      expect(await store.insert(submission({ runId }))).not.toBeNull();
      expect(await store.insert(submission({ runId }))).toBeNull();
      expect((await db.query("select count(*)::int as n from public.benchmark_submissions")).rows).toEqual([{ n: 1 }]);
    } finally {
      await db.close();
    }
  });

  it("rejects a provider outside the enum at the database", async () => {
    const { db, store } = await openStore();
    try {
      await expect(store.insert(submission({ provider: "mystery" }))).rejects.toThrow();
    } finally {
      await db.close();
    }
  });

  it("limits the number of rows returned and clamps absurd limits", async () => {
    const { db, store } = await openStore();
    try {
      await store.insert(submission({ modelName: "one", scores: scores(0.3) }));
      await store.insert(submission({ modelName: "two", scores: scores(0.4) }));
      await store.insert(submission({ provider: "openai", modelName: "three", scores: scores(0.5) }));
      expect(await store.leaderboard(2)).toHaveLength(2);
      expect(await store.leaderboard(0)).toHaveLength(1);
      expect(await store.leaderboard(Number.NaN)).toHaveLength(3);
    } finally {
      await db.close();
    }
  });
});
