import { agentSetupDatabase } from "@/lib/server/agent-setup-db";
import { handleAgentSetupMcp } from "@/lib/server/agent-setup-mcp";
import { limitOr429 } from "@/lib/server/limiter";
import { siteUrl } from "@/lib/site";

export async function POST(req: Request) {
  const origin = req.headers.get("origin");
  if (origin && origin !== siteUrl.origin && origin !== new URL(req.url).origin) {
    return new Response("Invalid origin.", { status: 403 });
  }
  const limited = await limitOr429(req, "setupMcp");
  if (limited) return limited;
  try {
    return await handleAgentSetupMcp(req, agentSetupDatabase());
  } catch {
    return Response.json({ error: "setup_unavailable" }, { status: 503, headers: { "cache-control": "no-store" } });
  }
}

export function GET() {
  return new Response(null, { status: 405, headers: { allow: "POST" } });
}
