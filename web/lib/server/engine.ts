import "server-only";
import { jsonError, NO_STORE_HEADERS } from "@/lib/http";
import { limitOr429 } from "@/lib/server/limiter";

const JOB_HEADER = "x-openbooks-job";
const JOB_KEY = /^[a-f0-9]{32}$/;

/** The engine service. Loopback only: the browser never talks to it directly. */
const ENGINE_URL = (process.env.OPENBOOKS_ENGINE_URL ?? "http://127.0.0.1:8765").replace(/\/+$/, "");

const ENGINE_KEY = process.env.OPENBOOKS_ENGINE_KEY ?? "";

// Connection-setup failures only: the request never reached the engine, so repeating it is safe.
// (undici's connect timeout is 10 s; the processing time is bounded by the caller's signal, not here.)
const SETUP_ERRORS = new Set(["ECONNREFUSED", "ECONNRESET", "ENOTFOUND", "EAI_AGAIN", "UND_ERR_CONNECT_TIMEOUT"]);
const SETUP_RETRIES = 2;
const SETUP_BACKOFF_MS = 250;

function failedBeforeSending(error: unknown): boolean {
  const code = (error as { cause?: { code?: string } })?.cause?.code;
  return typeof code === "string" && SETUP_ERRORS.has(code);
}

/** The tunnel key is scoped to the configured origin. Every call carries an x-request-id the engine echoes and logs. */
export async function engineFetch(path: `/v1/${string}`, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (ENGINE_KEY) headers.set("x-openbooks-key", ENGINE_KEY);
  if (!headers.has("x-request-id")) headers.set("x-request-id", crypto.randomUUID());
  // A streamed body cannot be replayed, so those requests are never retried.
  const replayable = !(init.body && typeof (init.body as ReadableStream).getReader === "function");
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await fetch(ENGINE_URL + path, { ...init, headers, redirect: "error" });
    } catch (error) {
      if (!replayable || attempt >= SETUP_RETRIES || init.signal?.aborted || !failedBeforeSending(error)) throw error;
      await new Promise((resolve) => setTimeout(resolve, SETUP_BACKOFF_MS * (attempt + 1)));
    }
  }
}

export function engineDown(): Response {
  return jsonError(502, "engine_unreachable", "The Open Books engine is temporarily unavailable.", NO_STORE_HEADERS);
}

const ENGINE_MEDIA = new Set(["application/json", "text/event-stream", "application/octet-stream"]);

export function relay(upstream: Response, extra: Record<string, string> = {}): Response {
  const media = upstream.headers.get("content-type")?.split(";")[0]?.trim().toLowerCase();
  if (upstream.body && (!media || !ENGINE_MEDIA.has(media))) {
    void upstream.body.cancel().catch(() => undefined);
    return engineDown();
  }
  const headers = new Headers();
  for (const h of ["content-type", "content-disposition", "cache-control", "retry-after", "x-request-id"]) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  for (const [name, value] of Object.entries(extra)) headers.set(name, value);
  return new Response(upstream.body, { status: upstream.status, headers });
}

/** Streams a multipart upload to the engine and relays its response. A caller that aborted gets 499. */
export async function proxyUpload(req: Request, path: `/v1/${string}`, extra: Record<string, string>): Promise<Response> {
  const headers = new Headers({ "content-type": req.headers.get("content-type") ?? "" });
  const job = req.headers.get(JOB_HEADER);
  if (job !== null) {
    if (!JOB_KEY.test(job)) return jsonError(400, "invalid_job_key", "Invalid upload job key.", NO_STORE_HEADERS);
    headers.set(JOB_HEADER, job);
  }
  try {
    const upstream = await engineFetch(path, {
      method: "POST",
      headers,
      body: req.body,
      signal: req.signal,
      // Required by Node's fetch to send a streaming request body.
      duplex: "half",
    } as RequestInit & { duplex: "half" });
    return relay(upstream, extra);
  } catch {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    return engineDown();
  }
}

/** The job key is a short-lived capability. Keep it out of URLs and shared caches. */
export async function proxyJobStatus(req: Request, path: "/v1/runs" | "/v1/roles"): Promise<Response> {
  const job = req.headers.get(JOB_HEADER);
  if (!job || !JOB_KEY.test(job)) return jsonError(400, "invalid_job_key", "Invalid upload job key.", NO_STORE_HEADERS);
  const cursor = new URL(req.url).searchParams.get("cursor") ?? "0";
  if (!/^\d{1,8}$/.test(cursor)) return jsonError(400, "invalid_cursor", "Invalid job cursor.", NO_STORE_HEADERS);
  const limited = await limitOr429(req, "jobStatus");
  if (limited) return limited;
  try {
    const upstream = await engineFetch(`${path}?cursor=${cursor}`, {
      headers: { [JOB_HEADER]: job }, signal: req.signal, cache: "no-store",
    });
    return relay(upstream, NO_STORE_HEADERS);
  } catch {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    return engineDown();
  }
}
