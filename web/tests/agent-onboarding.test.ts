import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";
import { describe, expect, it, vi } from "vitest";
import { createAgentSetupStore } from "@/lib/server/agent-setup-store";
import { handleAgentSetupMcp } from "@/lib/server/agent-setup-mcp";

describe("agent onboarding on isolated PostgreSQL", { timeout: 30_000 }, () => {
  it("confirms a real MCP tool call and isolates, expires and prunes receipts", async () => {
    const db = new PGlite();
    try {
      const migration = await readFile(new URL("../migrations/002_agent_onboarding.sql", import.meta.url), "utf8");
      await db.exec(migration);
      const store = createAgentSetupStore(async (text, params) => (await db.query<Record<string, unknown>>(text, params)).rows);
      const first = await store.create("codex");
      const second = await store.create("claude");
      expect(await store.status(first.watch)).toBe("waiting");
      expect(await store.status(first.code)).toBe("expired");
      expect(await store.confirm(first.watch)).toBe(false);

      async function mcp(method: string, params?: object) {
        const request = new Request("https://openbooks.example/api/agent/mcp", {
          method: "POST",
          headers: { accept: "application/json, text/event-stream", "content-type": "application/json" },
          body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
        });
        const response = await handleAgentSetupMcp(request, store);
        expect(response.status).toBe(200);
        return (await response.json()).result;
      }

      const connection = await mcp("initialize", {
        protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "test", version: "1" },
      });
      expect(connection.serverInfo.name).toBe("openbooks-agent-setup");
      const tools = await mcp("tools/list");
      expect(tools.tools.map((entry: { name: string }) => entry.name)).toEqual(["confirm_connection"]);

      const confirmation = await mcp("tools/call", {
        name: "confirm_connection", arguments: { code: first.code },
      });
      expect(confirmation.isError).toBe(false);
      expect(await store.status(first.watch)).toBe("connected");
      expect(await store.status(second.watch)).toBe("waiting");

      const snapshot = await db.query("select * from public.agent_onboarding");
      expect(JSON.stringify(snapshot.rows)).not.toContain(first.code);
      expect(JSON.stringify(snapshot.rows)).not.toContain(first.watch);
      expect(await store.confirm(first.code)).toBe(true);
      expect((await db.query("select verified_at from public.agent_onboarding where verified_at is not null")).rows).toHaveLength(1);

      await db.exec("update public.agent_onboarding set expires_at = now() - interval '1 second'");
      expect(await store.status(first.watch)).toBe("expired");
      expect(await store.confirm(first.code)).toBe(false);
      await store.create("hermes");
      expect((await db.query("select client from public.agent_onboarding")).rows).toEqual([{ client: "hermes" }]);
    } finally {
      await db.close();
    }
  });

  it("rejects oversized protocol requests before invoking a database operation", async () => {
    const confirm = vi.fn();
    const response = await handleAgentSetupMcp(new Request("https://openbooks.example/api/agent/mcp", {
      method: "POST", body: JSON.stringify({ raw: "0".repeat(9_000) }),
    }), { confirm });
    expect(response.status).toBe(413);
    expect(confirm).not.toHaveBeenCalled();
  });
});
