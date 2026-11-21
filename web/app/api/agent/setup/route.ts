import { z } from "zod";
import { AGENT_CLIENTS, SETUP_TOKEN } from "@/lib/agent-setup";
import { readSmallJson } from "@/lib/guards";
import { agentSetupDatabase } from "@/lib/server/agent-setup-db";
import { limitOr429 } from "@/lib/server/limiter";
import { siteUrl } from "@/lib/site";

const setupInput = z.discriminatedUnion("action", [
  z.object({ action: z.literal("start"), client: z.enum(AGENT_CLIENTS) }).strict(),
  z.object({ action: z.literal("status"), watch: z.string().regex(SETUP_TOKEN) }).strict(),
]);

function reply(body: object, status = 200) {
  return Response.json(body, { status, headers: { "cache-control": "no-store" } });
}

export async function POST(req: Request) {
  const origin = req.headers.get("origin");
  if (origin !== siteUrl.origin && origin !== new URL(req.url).origin) return reply({ error: "invalid_origin" }, 403);
  if (req.headers.get("content-type")?.split(";")[0]?.trim().toLowerCase() !== "application/json") {
    return reply({ error: "expected_json" }, 415);
  }

  const input = setupInput.safeParse(await readSmallJson(req, 1024).catch(() => null));
  if (!input.success) return reply({ error: "invalid_setup_request" }, 400);
  const limited = await limitOr429(req, input.data.action === "start" ? "setupStart" : "setupStatus");
  if (limited) return limited;

  try {
    const store = agentSetupDatabase();
    if (input.data.action === "start") return reply(await store.create(input.data.client), 201);
    return reply({ status: await store.status(input.data.watch) });
  } catch {
    return reply({ error: "setup_unavailable" }, 503);
  }
}
