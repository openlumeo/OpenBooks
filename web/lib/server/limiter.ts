import "server-only";
import { neon } from "@neondatabase/serverless";
import { jsonError, NO_STORE_HEADERS } from "@/lib/http";
import { createTokenBucket } from "@/lib/token-bucket";

export type Limit = { readonly capacity: number; readonly refillPerSec: number };
export type Verdict = { allowed: boolean; retryAfterSec: number };

/** Per-route limits. A "run" is one request, however many files it carries. */
export const LIMITS = {
  runs: { capacity: 10, refillPerSec: 1 / 20 },
  roles: { capacity: 20, refillPerSec: 1 / 10 },
  jobStatus: { capacity: 24, refillPerSec: 2 },
  link: { capacity: 30, refillPerSec: 1 / 5 },
  ask: { capacity: 10, refillPerSec: 1 / 30 }, // calls the paid LLM
  subscribe: { capacity: 5, refillPerSec: 1 / 60 },
  setupStart: { capacity: 8, refillPerSec: 1 / 30 },
  setupStatus: { capacity: 80, refillPerSec: 1 },
  setupMcp: { capacity: 40, refillPerSec: 1 / 2 },
} as const satisfies Record<string, Limit>;

/** Trust the final forwarded address added by the configured reverse proxy, not caller-supplied entries. */
export function clientKey(req: Request): string {
  if (process.env.NETLIFY === "true") return req.headers.get("x-nf-client-connection-ip")?.trim() || "unknown";
  const forwarded = req.headers.get("x-forwarded-for")?.split(",").at(-1)?.trim();
  return forwarded || "unknown";
}

// Local development can run without a database. Production must use shared state.
const local = new Map<string, ReturnType<typeof createTokenBucket>>();
function takeLocal(name: string, key: string, limit: Limit): Verdict {
  let bucket = local.get(name);
  if (!bucket) {
    bucket = createTokenBucket(limit);
    local.set(name, bucket);
  }
  return bucket.take(key);
}

const PRUNE_ODDS = 0.01;

/** Atomic shared token bucket in Neon (public.take_token), so every server instance draws from one bucket. */
export async function takeShared(name: string, key: string, limit: Limit): Promise<Verdict> {
  const url = process.env.DATABASE_URL;
  if (!url) {
    if (process.env.NODE_ENV === "production") throw new Error("Rate limiter database is not configured");
    return takeLocal(name, key, limit);
  }
  try {
    const sql = neon(url);
    const rows = await sql`select allowed, retry_after_sec from public.take_token(${`${name}:${key}`}, ${limit.capacity}, ${limit.refillPerSec})`;
    const row = rows[0] as { allowed: boolean; retry_after_sec: number } | undefined;
    if (!row) throw new Error("Rate limiter returned no verdict");
    if (Math.random() < PRUNE_ODDS) {
      void sql`delete from public.rate_buckets where updated_at < now() - interval '1 day'`.catch(() => undefined);
    }
    return { allowed: row.allowed, retryAfterSec: row.retry_after_sec };
  } catch (error: unknown) {
    console.error("limiter_db_error", error instanceof Error ? error.name : "unknown");
    if (process.env.NODE_ENV !== "production") return takeLocal(name, key, limit);
    throw error;
  }
}

/** Returns a 429 response when the caller is over the limit, otherwise null. */
export async function limitOr429(req: Request, name: keyof typeof LIMITS): Promise<Response | null> {
  let verdict: Verdict;
  try {
    verdict = await takeShared(name, clientKey(req), LIMITS[name]);
  } catch {
    return jsonError(503, "limiter_unavailable", "Please try again shortly.", NO_STORE_HEADERS);
  }
  if (verdict.allowed) return null;
  return Response.json(
    { error: "rate_limited", message: "You're going a little fast. Please wait a moment and try again.", retry_after_sec: verdict.retryAfterSec },
    { status: 429, headers: { "retry-after": String(verdict.retryAfterSec), "cache-control": "no-store" } },
  );
}
