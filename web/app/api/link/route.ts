import { MAX_JSON_BYTES, rejectOversize } from "@/lib/guards";
import { ENGINE_URL, engineDown, engineHeaders, relay } from "@/lib/server/engine";
import { limitOr429 } from "@/lib/server/limiter";

export async function POST(req: Request) {
  const limited = await limitOr429(req, "link");
  if (limited) return limited;
  const tooBig = rejectOversize(req, MAX_JSON_BYTES);
  if (tooBig) return tooBig;
  try {
    const upstream = await fetch(`${ENGINE_URL}/v1/link`, {
      method: "POST",
      headers: engineHeaders({ "content-type": "application/json" }),
      body: await req.text(),
    });
    return relay(upstream);
  } catch (err) {
    return engineDown(err);
  }
}
