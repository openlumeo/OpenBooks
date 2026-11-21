export const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_JSON_BYTES = 4 * 1024 * 1024;

export function rejectOversize(req: Request, maxBytes: number): Response | null {
  const raw = req.headers.get("content-length");
  const length = raw !== null && /^[0-9]+$/.test(raw) ? Number(raw) : Number.NaN;
  if (Number.isNaN(length)) {
    return Response.json({ error: "length_required", message: "Content-Length is required." }, { status: 411 });
  }
  if (length > maxBytes) {
    return Response.json(
      { error: "too_large", message: `The request is larger than the ${Math.floor(maxBytes / (1024 * 1024))} MB limit.` },
      { status: 413 },
    );
  }
  return null;
}

/** Cap the bytes read from callers that use chunked transfer or omit Content-Length. */
export async function readSmallJson(request: Request, maxBytes: number): Promise<unknown> {
  const reader = request.body?.getReader();
  if (!reader) throw new Error("invalid_json");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        void reader.cancel().catch(() => undefined);
        throw new Error("body_limit");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  return JSON.parse(Buffer.concat(chunks, size).toString("utf8"));
}

type Window = { start: number; count: number };

export function createRateLimiter(max: number, windowMs: number, now: () => number = Date.now) {
  let current: Window = { start: now(), count: 0 };
  return function limited(): boolean {
    const t = now();
    current = t - current.start >= windowMs ? { start: t, count: 1 } : { ...current, count: current.count + 1 };
    return current.count > max;
  };
}
