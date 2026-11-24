import { describe, expect, it } from "vitest";
import {
  AGENTS,
  AGENT_CHAT_PROMPT,
  CHECK_PROMPT,
  GOOSE_DEEPLINK,
  MCP_SERVERS_JSON,
  STDIO_SERVER,
  TRY_PROMPTS,
  cursorDeeplink,
  encodeBase64,
} from "@/components/onboard/onboard-data";

const ALLOWED_PLACEHOLDER = "/path/to/files";

function copyPayloads(): string[] {
  const cardCodes = AGENTS.flatMap((agent) => agent.cards.map((card) => card.code));
  return [...cardCodes, AGENT_CHAT_PROMPT, CHECK_PROMPT, ...TRY_PROMPTS.map((entry) => entry.prompt)];
}

describe("onboard data", () => {
  it("gives every client at least one install card", () => {
    for (const agent of AGENTS) {
      expect(agent.cards.length, agent.id).toBeGreaterThan(0);
    }
  });

  it("starts Claude Code, Codex and VS Code commands with their programs", () => {
    const byId = new Map(AGENTS.map((agent) => [agent.id, agent]));
    for (const card of byId.get("claude-code")?.cards ?? []) {
      expect(card.code.startsWith("claude mcp add openbooks -- npx -y -p @lumeo_hq/openbooks openbooks-mcp")).toBe(true);
    }
    for (const card of byId.get("codex")?.cards ?? []) {
      if (card.id === "add") expect(card.code.startsWith("codex ")).toBe(true);
    }
    expect(byId.get("vscode")?.cards[0]?.code.startsWith("code --add-mcp ")).toBe(true);
  });

  it("decodes the cursor deeplink config to the stdio server JSON", () => {
    const href = cursorDeeplink();
    const config = new URL(href).searchParams.get("config");
    expect(config).not.toBeNull();
    expect(JSON.parse(atob(config ?? ""))).toEqual(STDIO_SERVER);
    expect(atob(config ?? "")).toBe('{"command":"npx","args":["-y","-p","@lumeo_hq/openbooks","openbooks-mcp"]}');
    expect(href.startsWith("cursor://anysphere.cursor-deeplink/mcp/install?name=openbooks&config=")).toBe(true);
  });

  it("keeps the goose deeplink and the mcpServers JSON on the npx package", () => {
    expect(GOOSE_DEEPLINK.startsWith("goose://extension?cmd=npx")).toBe(true);
    expect(JSON.parse(MCP_SERVERS_JSON).mcpServers.openbooks).toEqual(STDIO_SERVER);
  });

  it("leaves no unfilled placeholders in copy payloads except the documented folder", () => {
    for (const payload of copyPayloads()) {
      const stripped = payload.split(ALLOWED_PLACEHOLDER).join("");
      expect(stripped, payload).not.toMatch(/<[a-z_][\w-]*>/i);
      expect(stripped, payload).not.toMatch(/\{\{|\}\}/);
      expect(stripped, payload).not.toMatch(/YOUR_|TODO|XXX|your-/i);
    }
  });

  it("has six unique try-it prompts", () => {
    expect(TRY_PROMPTS).toHaveLength(6);
    expect(new Set(TRY_PROMPTS.map((entry) => entry.prompt)).size).toBe(6);
    expect(new Set(TRY_PROMPTS.map((entry) => entry.id)).size).toBe(6);
  });
});
