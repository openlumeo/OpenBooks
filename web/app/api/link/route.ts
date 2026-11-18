import { MAX_JSON_BYTES, rejectOversize } from "@/lib/guards";
import { ENGINE_URL, engineDown, relay } from "@/lib/server/engine";

export async function POST(req: Request) {
  const tooBig = rejectOversize(req, MAX_JSON_BYTES);
  if (tooBig) return tooBig;
  try {
    const upstream = await fetch(`${ENGINE_URL}/v1/link`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await req.text(),
    });
    return relay(upstream);
  } catch (err) {
    return engineDown(err);
  }
}
