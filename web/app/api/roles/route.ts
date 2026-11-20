import { MAX_FILE_BYTES, rejectOversize } from "@/lib/guards";
import { ENGINE_URL, engineDown, engineHeaders, relay } from "@/lib/server/engine";
import { limitOr429 } from "@/lib/server/limiter";

export const dynamic = "force-dynamic";

/** The typed heads' own reading of one PDF or scan. Streams the multipart upload (file, params) to the engine. */
export async function POST(req: Request) {
  const limited = await limitOr429(req, "roles");
  if (limited) return limited;
  const type = req.headers.get("content-type") ?? "";
  if (!type.startsWith("multipart/form-data")) {
    return Response.json({ error: "bad_request", message: "expected a multipart upload" }, { status: 415 });
  }
  const tooBig = rejectOversize(req, MAX_FILE_BYTES);
  if (tooBig) return tooBig;
  try {
    const upstream = await fetch(`${ENGINE_URL}/v1/roles`, {
      method: "POST",
      headers: engineHeaders({ "content-type": type }),
      body: req.body,
      signal: req.signal,
      // Required by Node's fetch to send a streaming request body.
      duplex: "half",
    } as RequestInit & { duplex: "half" });
    return relay(upstream, { "cache-control": "no-store" });
  } catch (err) {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    return engineDown(err);
  }
}
