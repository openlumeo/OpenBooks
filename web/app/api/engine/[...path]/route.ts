import { ENGINE_URL, engineDown, relay } from "@/lib/server/engine";

// Read-only engine metadata. Only these paths are forwarded.
const ALLOWED = [/^health$/, /^formats$/, /^samples$/, /^samples\/[a-z0-9_]{1,80}$/];

export async function GET(_req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const path = (await ctx.params).path.join("/");
  if (!ALLOWED.some((re) => re.test(path))) {
    return Response.json({ error: "not_found" }, { status: 404 });
  }
  try {
    const upstream = await fetch(`${ENGINE_URL}/v1/${path}`, { cache: "no-store" });
    return relay(upstream);
  } catch (err) {
    return engineDown(err);
  }
}
