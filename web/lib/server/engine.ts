import "server-only";

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
  return Response.json(
    { error: "engine_unreachable", message: "The Open Books engine is temporarily unavailable." },
    { status: 502, headers: { "cache-control": "no-store" } },
  );
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
