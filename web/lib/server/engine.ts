import "server-only";

/** The engine service. Loopback only: the browser never talks to it directly. */
export const ENGINE_URL = (process.env.OPENBOOKS_ENGINE_URL ?? "http://127.0.0.1:8765").replace(/\/+$/, "");

const ENGINE_KEY = process.env.OPENBOOKS_ENGINE_KEY ?? "";

/** Headers for every engine request. The key authenticates this site to the engine's public tunnel. */
export function engineHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return ENGINE_KEY ? { ...extra, "x-openbooks-key": ENGINE_KEY } : extra;
}

export function engineDown(err: unknown): Response {
  const detail = err instanceof Error ? err.message : String(err);
  return Response.json(
    { error: "engine_unreachable", message: `The Open Books engine is not reachable at ${ENGINE_URL}.`, detail },
    { status: 502 },
  );
}

/** Copy an upstream response, keeping only headers that are safe and meaningful to pass on. */
export function relay(upstream: Response, extra: Record<string, string> = {}): Response {
  const headers = new Headers(extra);
  for (const h of ["content-type", "content-disposition", "cache-control"]) {
    const v = upstream.headers.get(h);
    if (v) headers.set(h, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}
