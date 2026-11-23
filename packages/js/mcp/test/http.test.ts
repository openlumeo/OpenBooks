import { request } from "node:http";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { findEngine, runFile } from "@lumeo_hq/openbooks-core";
import { MAX_HTTP_BODY_BYTES, MIN_TOKEN_LENGTH } from "../src/constants.js";
import { startHttp, type RunningHttpServer } from "../src/http.js";
import { ENGINE, released } from "./helpers.js";

vi.mock("@lumeo_hq/openbooks-core", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@lumeo_hq/openbooks-core")>()),
  runFile: vi.fn(),
  findEngine: vi.fn(),
}));

const compare = vi.hoisted(() => ({ calls: 0 }));
vi.mock("node:crypto", async (importOriginal) => {
  const original = await importOriginal<typeof import("node:crypto")>();
  return {
    ...original,
    timingSafeEqual: (a: NodeJS.ArrayBufferView, b: NodeJS.ArrayBufferView) => {
      compare.calls += 1;
      return original.timingSafeEqual(a, b);
    },
  };
});

const TOKEN = "t".repeat(MIN_TOKEN_LENGTH);
const SAME_LENGTH_WRONG = "u".repeat(MIN_TOKEN_LENGTH);
const ACCEPT = "application/json, text/event-stream";
const initialize = { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "t", version: "1" } } };

let server: RunningHttpServer;
let base: string;

beforeAll(async () => {
  server = await startHttp({ port: 0, token: TOKEN });
  base = `http://127.0.0.1:${server.port}`;
});

afterAll(async () => {
  await server.close();
});

beforeEach(() => {
  compare.calls = 0;
  vi.mocked(findEngine).mockResolvedValue(ENGINE);
  vi.mocked(runFile).mockImplementation(async () => released("statement.csv"));
});

interface Sent {
  path?: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}

async function send(options: Sent = {}): Promise<{ status: number; text: string; headers: Headers }> {
  const method = options.method ?? "POST";
  const init: RequestInit = { method, headers: { Accept: ACCEPT, "Content-Type": "application/json", ...options.headers } };
  if (method !== "GET" && method !== "HEAD") init.body = options.body ?? JSON.stringify(initialize);
  const response = await fetch(`${base}${options.path ?? "/mcp"}`, init);
  return { status: response.status, text: await response.text(), headers: response.headers };
}

const auth = (token = TOKEN): Record<string, string> => ({ Authorization: `Bearer ${token}` });

interface Rpc {
  result?: { protocolVersion?: string; tools?: { name: string }[] };
}

function rpcResult(text: string): Rpc {
  const line = text.split("\n").find((entry) => entry.startsWith("data:"));
  return JSON.parse(line === undefined ? text : line.slice(5).trim()) as Rpc;
}

describe("token policy", () => {
  it.each([
    ["empty", ""],
    ["short", "short"],
    ["one under the minimum", "a".repeat(MIN_TOKEN_LENGTH - 1)],
    ["contains a space", `${"a".repeat(MIN_TOKEN_LENGTH)} b`],
    ["contains a newline", `${"a".repeat(MIN_TOKEN_LENGTH)}\n`],
    ["contains non-ASCII", `${"a".repeat(MIN_TOKEN_LENGTH)}é`],
  ])("startHttp throws for a %s token", async (_label, token) => {
    await expect(startHttp({ port: 0, token })).rejects.toThrow(/at least 32/);
  });

  it("accepts a token of exactly the minimum length", async () => {
    const running = await startHttp({ port: 0, token: "x".repeat(MIN_TOKEN_LENGTH) });
    await running.close();
  });
});

describe("authentication", () => {
  it.each([
    ["no header", {}],
    ["wrong token of the same length", auth(SAME_LENGTH_WRONG)],
    ["wrong token of a different length", auth("short")],
    ["empty bearer value", { Authorization: "Bearer " }],
    ["basic scheme", { Authorization: `Basic ${TOKEN}` }],
    ["lowercase scheme", { Authorization: `bearer ${TOKEN}` }],
    ["token without scheme", { Authorization: TOKEN }],
  ])("returns 401 for %s", async (_label, headers) => {
    const response = await send({ headers });
    expect(response.status).toBe(401);
    expect(response.headers.get("www-authenticate")).toBe("Bearer");
  });

  it("compares same-length tokens with timingSafeEqual", async () => {
    await send({ headers: auth(SAME_LENGTH_WRONG) });
    expect(compare.calls).toBe(1);
  });

  it("skips timingSafeEqual for different-length tokens", async () => {
    await send({ headers: auth("short") });
    expect(compare.calls).toBe(0);
  });

  it("does not echo the token in error bodies", async () => {
    const response = await send({ headers: auth(SAME_LENGTH_WRONG) });
    expect(response.text).not.toContain(SAME_LENGTH_WRONG);
  });

  it("sets no-store on errors", async () => {
    expect((await send()).headers.get("cache-control")).toBe("no-store");
  });
});

describe("origin, method and path checks", () => {
  it.each(["https://evil.example", "http://localhost.evil.example", "http://127.0.0.2:3000", "null", "not a url"])("returns 403 for origin %s", async (origin) => {
    expect((await send({ headers: { ...auth(), Origin: origin } })).status).toBe(403);
  });

  it.each(["http://localhost:3000", "http://127.0.0.1:8080"])("allows origin %s", async (origin) => {
    expect((await send({ headers: { ...auth(), Origin: origin } })).status).toBe(200);
  });

  it.each(["GET", "PUT", "DELETE", "PATCH"])("returns 405 for %s", async (method) => {
    const response = await send({ method, headers: auth() });
    expect(response.status).toBe(405);
    expect(response.headers.get("allow")).toBe("POST");
  });

  it.each(["/", "/mcp/", "/other", "/mcp/extra", "/MCP"])("returns 404 for path %s", async (path) => {
    expect((await send({ path, headers: auth() })).status).toBe(404);
  });

  it("returns 404 before checking the token", async () => {
    expect((await send({ path: "/other" })).status).toBe(404);
  });

  it("accepts a query string on the mcp path", async () => {
    expect((await send({ path: "/mcp?x=1", headers: auth() })).status).toBe(200);
  });
});

describe("request bodies", () => {
  it("returns 413 above the body limit", async () => {
    const body = JSON.stringify({ pad: "x".repeat(MAX_HTTP_BODY_BYTES + 1024) });
    const status = await new Promise<number>((resolve, reject) => {
      const req = request(
        { host: "127.0.0.1", port: server.port, path: "/mcp", method: "POST", headers: { ...auth(), "Content-Type": "application/json", Accept: ACCEPT } },
        (res) => {
          res.resume();
          resolve(res.statusCode ?? 0);
        },
      );
      req.on("error", reject);
      req.end(body);
    });
    expect(status).toBe(413);
  });

  it.each(["{not json", "", "plain text"])("returns 400 for invalid JSON %j", async (body) => {
    expect((await send({ headers: auth(), body })).status).toBe(400);
  });
});

describe("MCP over HTTP", () => {
  it("answers initialize", async () => {
    const response = await send({ headers: auth() });
    expect(response.status).toBe(200);
    expect(rpcResult(response.text).result?.protocolVersion).toBeTruthy();
  });

  it("lists the two tools", async () => {
    const response = await send({ headers: auth(), body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" }) });
    expect(rpcResult(response.text).result?.tools?.map((tool) => tool.name).sort()).toEqual(["execute", "search"]);
  });

  it("does not expose process_file", async () => {
    const body = JSON.stringify({ jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "execute", arguments: { steps: [{ id: "a", operation: "process_file", arguments: { path: "a.csv" } }] } } });
    expect((await send({ headers: auth(), body })).text).toContain("UNKNOWN_OPERATION");
  });

  it("runs verify_many uploads", async () => {
    const upload = { filename: "u.csv", content_base64: Buffer.from("a,b\n").toString("base64") };
    const body = JSON.stringify({ jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "execute", arguments: { steps: [{ id: "v", operation: "verify_many", arguments: { uploads: [upload] } }] } } });
    expect((await send({ headers: auth(), body })).text).toContain('"ok":1');
  });
});
