import { jsonError } from "@/lib/http";

export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024;
export const MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024;
export const MAX_JSON_BYTES = 4 * 1024 * 1024;

const BYTES_PER_MB = 1024 * 1024;

export function rejectOversize(req: Request, maxBytes: number): Response | null {
  const raw = req.headers.get("content-length");
  const length = raw !== null && /^[0-9]+$/.test(raw) ? Number(raw) : Number.NaN;
  if (Number.isNaN(length)) {
    return jsonError(411, "length_required", "Content-Length is required.");
  }
  if (length > maxBytes) {
    return jsonError(413, "too_large", `The request is larger than the ${Math.floor(maxBytes / BYTES_PER_MB)} MB limit.`);
  }
  return null;
}

export function rejectNonMultipart(contentType: string): Response | null {
  if (contentType.startsWith("multipart/form-data")) return null;
  return jsonError(415, "bad_request", "expected a multipart upload");
}

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
