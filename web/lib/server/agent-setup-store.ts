import { createHash, randomBytes } from "node:crypto";
import { AGENT_CLIENTS, SETUP_MINUTES, type AgentClient } from "@/lib/agent-setup";

type Query = (text: string, params?: unknown[]) => Promise<Record<string, unknown>[]>;

export type AgentSetupStore = ReturnType<typeof createAgentSetupStore>;

function digest(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

export function createAgentSetupStore(query: Query) {
  return {
    async create(client: AgentClient) {
      if (!AGENT_CLIENTS.includes(client)) throw new Error("invalid_client");
      const watch = randomBytes(24).toString("base64url");
      const code = randomBytes(24).toString("base64url");
      const rows = await query(
        `WITH expired AS (
           DELETE FROM public.agent_onboarding WHERE expires_at < now()
         )
         INSERT INTO public.agent_onboarding (watch_hash, code_hash, client, expires_at)
           VALUES ($1, $2, $3, now() + $4 * interval '1 minute')
           RETURNING expires_at`,
        [digest(watch), digest(code), client, SETUP_MINUTES],
      );
      const expiration = rows[0]?.expires_at as string | Date;
      return { watch, code, expiresAt: new Date(expiration).toISOString() };
    },
    async status(watch: string): Promise<"waiting" | "connected" | "expired"> {
      const rows = await query(
        `SELECT verified_at FROM public.agent_onboarding
           WHERE watch_hash = $1 AND expires_at > now()`,
        [digest(watch)],
      );
      if (!rows[0]) return "expired";
      return rows[0].verified_at ? "connected" : "waiting";
    },
    async confirm(code: string): Promise<boolean> {
      const rows = await query(
        `UPDATE public.agent_onboarding
           SET verified_at = COALESCE(verified_at, now())
           WHERE code_hash = $1 AND expires_at > now()
           RETURNING verified_at`,
        [digest(code)],
      );
      return rows.length === 1;
    },
  };
}
