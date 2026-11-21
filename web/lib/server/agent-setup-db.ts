import "server-only";
import { neon } from "@neondatabase/serverless";
import { createAgentSetupStore } from "./agent-setup-store";

export function agentSetupDatabase() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("Database is not configured");
  const sql = neon(url);
  return createAgentSetupStore((text, params) => sql.query(text, params));
}
