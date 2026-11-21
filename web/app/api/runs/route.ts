import { MAX_UPLOAD_BYTES, rejectOversize } from "@/lib/guards";
import { engineDown, engineFetch, relay } from "@/lib/server/engine";
import { limitOr429 } from "@/lib/server/limiter";

export const dynamic = "force-dynamic";

/** Streams the multipart upload straight to the engine and the engine's SSE straight back. */
export async function POST(req: Request) {
  const limited = await limitOr429(req, "runs");
  if (limited) return limited;
  const type = req.headers.get("content-type") ?? "";
  if (!type.startsWith("multipart/form-data")) {
    return Response.json({ error: "bad_request", message: "expected a multipart upload" }, { status: 415 });
  }
  const tooBig = rejectOversize(req, MAX_UPLOAD_BYTES);
  if (tooBig) return tooBig;
  try {
    const upstream = await engineFetch("/v1/runs", {
      method: "POST",
      headers: { "content-type": type },
      body: req.body,
      signal: req.signal,
      // Required by Node's fetch to send a streaming request body.
      duplex: "half",
    } as RequestInit & { duplex: "half" });
    return relay(upstream, { "cache-control": "no-store", "x-accel-buffering": "no" });
  } catch {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    return engineDown();
  }
}
