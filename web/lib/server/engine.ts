import "server-only";

/** The engine service. Loopback only: the browser never talks to it directly. */
const ENGINE_URL = (process.env.OPENBOOKS_ENGINE_URL ?? "http://127.0.0.1:8765").replace(/\/+$/, "");

const ENGINE_KEY = process.env.OPENBOOKS_ENGINE_KEY ?? "";

/** The tunnel key is scoped to the configured origin. */
export function engineFetch(path: `/v1/${string}`, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (ENGINE_KEY) headers.set("x-openbooks-key", ENGINE_KEY);
  return fetch(ENGINE_URL + path, { ...init, headers, redirect: "error" });
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
  for (const h of ["content-type", "content-disposition", "cache-control"]) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  for (const [name, value] of Object.entries(extra)) headers.set(name, value);
  return new Response(upstream.body, { status: upstream.status, headers });
}
