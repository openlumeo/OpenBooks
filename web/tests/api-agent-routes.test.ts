import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const limiter = vi.hoisted(() => ({ limitOr429: vi.fn() }));
vi.mock("@/lib/server/limiter", () => limiter);
const setupDb = vi.hoisted(() => ({ agentSetupDatabase: vi.fn(), create: vi.fn(), status: vi.fn(), confirm: vi.fn() }));
vi.mock("@/lib/server/agent-setup-db", () => ({ agentSetupDatabase: setupDb.agentSetupDatabase }));

import * as setupRoute from "@/app/api/agent/setup/route";
import * as mcpRoute from "@/app/api/agent/mcp/route";

const SITE = "https://openbooks.openlumeo.com";
const TOKEN = "a".repeat(32);
const MCP_HEADERS = { accept: "application/json, text/event-stream", "content-type": "application/json" };

function setup(body: string, headers: Record<string, string> = {}): Request {
  return new Request("http://localhost/api/agent/setup", {
    method: "POST",
    headers: { "content-type": "application/json", origin: SITE, ...headers },
    body,
  });
}

function mcp(body: string, headers: Record<string, string> = MCP_HEADERS): Request {
  return new Request("http://localhost/api/agent/mcp", { method: "POST", headers, body });
}

beforeEach(() => {
  limiter.limitOr429.mockReset();
  limiter.limitOr429.mockResolvedValue(null);
  setupDb.agentSetupDatabase.mockReset();
  setupDb.agentSetupDatabase.mockReturnValue({ create: setupDb.create, status: setupDb.status, confirm: setupDb.confirm });
  setupDb.create.mockReset();
  setupDb.status.mockReset();
  setupDb.confirm.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("POST /api/agent/setup", () => {
  it("creates a setup code for a known client and answers 201 no-store", async () => {
    setupDb.create.mockResolvedValueOnce({ watch: TOKEN, expiresInMinutes: 10 });
    const res = await setupRoute.POST(setup('{"action":"start","client":"claude"}'));
    expect(res.status).toBe(201);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.json()).toEqual({ watch: TOKEN, expiresInMinutes: 10 });
    expect(setupDb.create).toHaveBeenCalledWith("claude");
    expect(limiter.limitOr429).toHaveBeenCalledWith(expect.any(Request), "setupStart");
  });

  it("reports the status of a watched setup code with a 200 no-store", async () => {
    setupDb.status.mockResolvedValueOnce("pending");
    const res = await setupRoute.POST(setup(JSON.stringify({ action: "status", watch: TOKEN })));
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.json()).toEqual({ status: "pending" });
    expect(limiter.limitOr429).toHaveBeenCalledWith(expect.any(Request), "setupStatus");
  });

  it("accepts a JSON content-type with a charset parameter", async () => {
    setupDb.create.mockResolvedValueOnce({ watch: TOKEN });
    const res = await setupRoute.POST(setup('{"action":"start","client":"codex"}', { "content-type": "Application/JSON; charset=utf-8" }));
    expect(res.status).toBe(201);
  });

  it("accepts a request whose origin matches the request URL origin", async () => {
    setupDb.create.mockResolvedValueOnce({ watch: TOKEN });
    const req = new Request("http://localhost/api/agent/setup", {
      method: "POST",
      headers: { "content-type": "application/json", origin: "http://localhost" },
      body: '{"action":"start","client":"grok"}',
    });
    expect((await setupRoute.POST(req)).status).toBe(201);
  });

  it.each([
    ["a cross-site origin", { origin: "https://evil.example" }],
    ["a suffix-spoofed origin", { origin: "https://openbooks.openlumeo.com.evil.example" }],
    ["a http downgrade of the site origin", { origin: "http://openbooks.openlumeo.com" }],
    ["a missing origin", { origin: undefined }],
  ])("answers 403 invalid_origin for %s without touching the database", async (_label, override) => {
    const headers: Record<string, string | undefined> = { "content-type": "application/json", ...override };
    const req = new Request("http://localhost/api/agent/setup", {
      method: "POST",
      headers: Object.fromEntries(Object.entries(headers).filter(([, v]) => v !== undefined)) as Record<string, string>,
      body: '{"action":"start","client":"claude"}',
    });
    const res = await setupRoute.POST(req);
    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({ error: "invalid_origin" });
    expect(setupDb.create).not.toHaveBeenCalled();
  });

  it.each([
    ["text/plain", "text/plain"],
    ["multipart form data", "multipart/form-data; boundary=x"],
    ["a missing content-type", undefined],
  ])("answers 415 expected_json for %s", async (_label, contentType) => {
    const headers: Record<string, string> = { origin: SITE };
    if (contentType) headers["content-type"] = contentType;
    const req = new Request("http://localhost/api/agent/setup", {
      method: "POST",
      headers,
      body: '{"action":"start","client":"claude"}',
    });
    const res = await setupRoute.POST(req);
    expect(res.status).toBe(415);
    expect(await res.json()).toEqual({ error: "expected_json" });
  });

  it.each([
    ["an empty body", ""],
    ["malformed JSON", "{nope"],
    ["a non-object JSON value", "42"],
    ["an unknown action", '{"action":"delete"}'],
    ["an unknown client", '{"action":"start","client":"mallory"}'],
    ["an extra property", '{"action":"start","client":"claude","role":"admin"}'],
    ["a watch token that is too short", '{"action":"status","watch":"short"}'],
    ["a watch token with disallowed characters", `{"action":"status","watch":"${"!".repeat(32)}"}`],
    ["a watch token over the length", `{"action":"status","watch":"${"a".repeat(33)}"}`],
    ["a missing client", '{"action":"start"}'],
    ["a body over the 1 KB cap", JSON.stringify({ action: "start", client: "claude", pad: "x".repeat(1100) })],
  ])("answers 400 invalid_setup_request for %s", async (_label, body) => {
    const res = await setupRoute.POST(setup(body));
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: "invalid_setup_request" });
    expect(setupDb.create).not.toHaveBeenCalled();
    expect(setupDb.status).not.toHaveBeenCalled();
  });

  it("answers 429 with Retry-After when the limiter refuses the caller", async () => {
    limiter.limitOr429.mockResolvedValueOnce(
      Response.json({ error: "rate_limited" }, { status: 429, headers: { "retry-after": "30", "cache-control": "no-store" } }),
    );
    const res = await setupRoute.POST(setup('{"action":"start","client":"claude"}'));
    expect(res.status).toBe(429);
    expect(res.headers.get("retry-after")).toBe("30");
    expect(setupDb.create).not.toHaveBeenCalled();
  });

  it("answers 503 setup_unavailable when the database is not configured, without naming the setting", async () => {
    setupDb.agentSetupDatabase.mockImplementationOnce(() => {
      throw new Error("Database is not configured");
    });
    const res = await setupRoute.POST(setup('{"action":"start","client":"claude"}'));
    expect(res.status).toBe(503);
    expect(res.headers.get("cache-control")).toBe("no-store");
    const body = await res.text();
    expect(JSON.parse(body)).toEqual({ error: "setup_unavailable" });
    expect(body).not.toContain("DATABASE_URL");
  });

  it("answers 503 without leaking a connection string when the store write fails", async () => {
    setupDb.create.mockRejectedValueOnce(new Error("connect ECONNREFUSED postgres://user:hunter2@db.internal/app"));
    const res = await setupRoute.POST(setup('{"action":"start","client":"claude"}'));
    expect(res.status).toBe(503);
    const body = await res.text();
    expect(body).not.toContain("hunter2");
    expect(body).not.toContain("db.internal");
    expect(body).not.toContain("ECONNREFUSED");
  });

  it("does not export GET, so it is answered 405 by Next", () => {
    expect(Object.keys(setupRoute).filter((k) => /^[A-Z]+$/.test(k))).toEqual(["POST"]);
  });
});

describe("POST /api/agent/mcp", () => {
  it("answers the MCP initialize request with the server name", async () => {
    const init = { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "test", version: "1" } } };
    const res = await mcpRoute.POST(mcp(JSON.stringify(init)));
    expect(res.status).toBe(200);
    const payload = JSON.parse(await res.text()) as { result?: { serverInfo?: { name: string } } };
    expect(payload.result?.serverInfo?.name).toBe("openbooks-agent-setup");
  });

  it("lists only the confirm_connection tool", async () => {
    const list = { jsonrpc: "2.0", id: 2, method: "tools/list" };
    const res = await mcpRoute.POST(mcp(JSON.stringify(list)));
    const text = await res.text();
    expect(text).toContain("confirm_connection");
    expect(text).not.toContain("delete");
  });

  it("confirms a valid setup code through the store", async () => {
    setupDb.confirm.mockResolvedValueOnce(true);
    const call = { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "confirm_connection", arguments: { code: TOKEN } } };
    const text = await (await mcpRoute.POST(mcp(JSON.stringify(call)))).text();
    expect(setupDb.confirm).toHaveBeenCalledWith(TOKEN);
    expect(text).toContain("setup connection verified");
  });

  it("reports an expired or unknown code as an error result, not a server failure", async () => {
    setupDb.confirm.mockResolvedValueOnce(false);
    const call = { jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "confirm_connection", arguments: { code: TOKEN } } };
    const text = await (await mcpRoute.POST(mcp(JSON.stringify(call)))).text();
    expect(text).toContain("expired or is invalid");
    expect(text).toContain("isError");
  });

  it("answers JSON-RPC parse error -32700 for malformed JSON with status 400", async () => {
    const res = await mcpRoute.POST(mcp("{nope"));
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Invalid JSON." } });
  });

  it("answers 413 for a body over the 8 KB MCP cap", async () => {
    const res = await mcpRoute.POST(mcp(JSON.stringify({ jsonrpc: "2.0", id: 5, method: "tools/list", pad: "x".repeat(9000) })));
    expect(res.status).toBe(413);
    expect(await res.json()).toEqual({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "MCP body is too large." } });
  });

  it("answers 400 for an empty body", async () => {
    expect((await mcpRoute.POST(mcp(""))).status).toBe(400);
  });

  it("rejects a confirm_connection code that does not match the setup token format", async () => {
    const call = { jsonrpc: "2.0", id: 6, method: "tools/call", params: { name: "confirm_connection", arguments: { code: "not-a-token" } } };
    const text = await (await mcpRoute.POST(mcp(JSON.stringify(call)))).text();
    expect(setupDb.confirm).not.toHaveBeenCalled();
    expect(text).toMatch(/error|invalid/i);
  });

  it("rejects a cross-site origin with 403 before reading the body or the limiter", async () => {
    const res = await mcpRoute.POST(mcp("{}", { ...MCP_HEADERS, origin: "https://evil.example" }));
    expect(res.status).toBe(403);
    expect(await res.text()).toBe("Invalid origin.");
    expect(limiter.limitOr429).not.toHaveBeenCalled();
  });

  it("accepts a request whose origin is the site origin", async () => {
    const res = await mcpRoute.POST(mcp(JSON.stringify({ jsonrpc: "2.0", id: 7, method: "tools/list" }), { ...MCP_HEADERS, origin: SITE }));
    expect(res.status).toBe(200);
  });

  it("answers 429 with Retry-After when the limiter refuses the caller", async () => {
    limiter.limitOr429.mockResolvedValueOnce(
      Response.json({ error: "rate_limited" }, { status: 429, headers: { "retry-after": "12", "cache-control": "no-store" } }),
    );
    const res = await mcpRoute.POST(mcp("{}"));
    expect(res.status).toBe(429);
    expect(res.headers.get("retry-after")).toBe("12");
    expect(limiter.limitOr429).toHaveBeenCalledWith(expect.any(Request), "setupMcp");
  });

  it("answers 503 setup_unavailable with no-store and no internal detail when the database is unavailable", async () => {
    setupDb.agentSetupDatabase.mockImplementationOnce(() => {
      throw new Error("Database is not configured");
    });
    const res = await mcpRoute.POST(mcp(JSON.stringify({ jsonrpc: "2.0", id: 8, method: "tools/list" })));
    expect(res.status).toBe(503);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.text()).not.toContain("Database");
  });

  it("answers GET with 405 and Allow: POST", async () => {
    const res = mcpRoute.GET();
    expect(res.status).toBe(405);
    expect(res.headers.get("allow")).toBe("POST");
  });
});
