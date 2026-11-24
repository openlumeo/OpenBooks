import "server-only";
import { neon } from "@neondatabase/serverless";
import { jsonError, NO_STORE_HEADERS } from "@/lib/http";
import { clientKey, takeShared } from "@/lib/server/limiter";
import { knownTaskSets } from "@/lib/benchmark/task-sets";
import { createBenchmarkStore, type BenchmarkStore } from "@/lib/benchmark/store";
import type { SubmitDeps } from "@/lib/benchmark/submit";

const SUBMIT_LIMIT = { capacity: 6, refillPerSec: 1 / 300 } as const;
export const LEADERBOARD_CACHE = "public, s-maxage=300, stale-while-revalidate=600";

function benchmarkStore(): BenchmarkStore {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("Database is not configured");
  const sql = neon(url);
  return createBenchmarkStore((text, params) => sql.query(text, params) as Promise<Record<string, unknown>[]>);
}

async function rateLimitSubmit(req: Request): Promise<Response | null> {
  let verdict: { allowed: boolean; retryAfterSec: number };
  try {
    verdict = await takeShared("benchmarkSubmit", clientKey(req), SUBMIT_LIMIT);
  } catch {
    return jsonError(503, "limiter_unavailable", "Please try again shortly.", NO_STORE_HEADERS);
  }
  if (verdict.allowed) return null;
  return Response.json(
    { error: "rate_limited", message: "Too many submissions. Please wait and try again.", retry_after_sec: verdict.retryAfterSec },
    { status: 429, headers: { "retry-after": String(verdict.retryAfterSec), ...NO_STORE_HEADERS } },
  );
}

export function submitDeps(): SubmitDeps {
  return {
    rateLimit: rateLimitSubmit,
    store: { insert: (record) => benchmarkStore().insert(record) },
    taskSets: knownTaskSets,
  };
}

export function loadLeaderboard(limit?: number) {
  return benchmarkStore().leaderboard(limit);
}
