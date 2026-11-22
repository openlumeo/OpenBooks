import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const limiter = vi.hoisted(() => ({ limitOr429: vi.fn() }));
vi.mock("@/lib/server/limiter", () => limiter);
const upstream = vi.hoisted(() => ({ engineFetch: vi.fn() }));
vi.mock("@/lib/server/engine", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/server/engine")>()),
  engineFetch: upstream.engineFetch,
}));

import * as engineRoute from "@/app/api/engine/[...path]/route";

const { GET } = engineRoute;

function call(segments: string[], init: { url?: string; signal?: AbortSignal } = {}): Promise<Response> {
  const url = init.url ?? "http://localhost/api/engine/" + segments.join("/");
  return GET(new Request(url, { signal: init.signal }), { params: Promise.resolve({ path: segments }) });
}

function engineReply(body: string, headers: Record<string, string> = { "content-type": "application/json" }, status = 200): Response {
  return new Response(body, { status, headers });
}

beforeEach(() => {
  upstream.engineFetch.mockReset();
  limiter.limitOr429.mockReset();
  limiter.limitOr429.mockResolvedValue(null);
});

describe("GET /api/engine/[...path] allowlist", () => {
  it.each([
    [["health"], "/v1/health"],
    [["formats"], "/v1/formats"],
    [["samples"], "/v1/samples"],
    [["samples", "bank_statement_01"], "/v1/samples/bank_statement_01"],
    [["samples", "a"], "/v1/samples/a"],
  ])("forwards the allowed read-only path %j as %s", async (segments, expected) => {
    upstream.engineFetch.mockResolvedValueOnce(engineReply('{"ok":true}'));
    const res = await call(segments);
    expect(res.status).toBe(200);
    expect(upstream.engineFetch).toHaveBeenCalledTimes(1);
    expect(upstream.engineFetch.mock.calls[0]?.[0]).toBe(expected);
  });

  it.each([
    ["an unlisted path", ["admin"]],
    ["the runs endpoint", ["runs"]],
    ["the roles endpoint", ["roles"]],
    ["a POST-only upload path", ["upload"]],
    ["extra segments after health", ["health", "extra"]],
    ["an uppercase path", ["HEALTH"]],
    ["an uppercase sample name", ["samples", "Bank"]],
    ["a sample name over 80 characters", ["samples", "a".repeat(81)]],
    ["an empty sample name", ["samples", ""]],
    ["a sample name containing a slash", ["samples", "a/b"]],
    ["a sample name with a hyphen", ["samples", "a-b"]],
    ["a parent-directory traversal", ["..", "health"]],
    ["an encoded parent-directory traversal left undecoded", ["%2e%2e", "health"]],
    ["a traversal inside the sample path", ["samples", "..", "health"]],
    ["a traversal with a backslash", ["..\\health"]],
    ["a double slash before the path", ["", "health"]],
    ["a trailing slash", ["health", ""]],
    ["a query string smuggled into the segment", ["health?admin=1"]],
    ["a fragment smuggled into the segment", ["health#admin"]],
    ["a trailing newline", ["health\n"]],
    ["an encoded newline", ["health%0a"]],
    ["a unicode look-alike", ["hеalth"]],
    ["a very long unknown segment", ["x".repeat(10_000)]],
  ])("answers 404 not_found for %s and never calls the engine", async (_label, segments) => {
    const res = await call(segments);
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: "not_found" });
    expect(upstream.engineFetch).not.toHaveBeenCalled();
  });

  it("does not echo the rejected path back in the 404 body", async () => {
    const res = await call(["..", "secret-admin-probe"]);
    expect(await res.text()).not.toContain("secret-admin-probe");
  });

  it("ignores the query string and forwards only the path", async () => {
    upstream.engineFetch.mockResolvedValueOnce(engineReply("{}"));
    await call(["health"], { url: "http://localhost/api/engine/health?admin=true&x=../../runs" });
    expect(upstream.engineFetch.mock.calls[0]?.[0]).toBe("/v1/health");
  });
});

describe("GET /api/engine/[...path] relay", () => {
  it("relays the engine content-type and body", async () => {
    upstream.engineFetch.mockResolvedValueOnce(engineReply('{"formats":["csv"]}'));
    const res = await call(["formats"]);
    expect(res.headers.get("content-type")).toBe("application/json");
    expect(await res.json()).toEqual({ formats: ["csv"] });
  });

  it("accepts a JSON content-type that carries a charset parameter", async () => {
    upstream.engineFetch.mockResolvedValueOnce(engineReply("{}", { "content-type": "Application/JSON; charset=utf-8" }));
    expect((await call(["health"])).status).toBe(200);
  });

  it("relays the engine's status code, such as 404 for an unknown sample", async () => {
    upstream.engineFetch.mockResolvedValueOnce(engineReply('{"error":"unknown_sample"}', { "content-type": "application/json" }, 404));
    const res = await call(["samples", "missing_sample"]);
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: "unknown_sample" });
  });

  it("relays the engine's cache-control and does not invent one", async () => {
    upstream.engineFetch.mockResolvedValueOnce(
      new Response("{}", { headers: { "content-type": "application/json", "cache-control": "max-age=60" } }),
    );
    expect((await call(["health"])).headers.get("cache-control")).toBe("max-age=60");
    upstream.engineFetch.mockResolvedValueOnce(engineReply("{}"));
    expect((await call(["health"])).headers.get("cache-control")).toBeNull();
  });

  it("relays an event-stream content-type", async () => {
    upstream.engineFetch.mockResolvedValueOnce(engineReply("data: 1\n\n", { "content-type": "text/event-stream" }));
    expect((await call(["health"])).headers.get("content-type")).toBe("text/event-stream");
  });

  it.each([
    ["text/html", { "content-type": "text/html; charset=utf-8" }],
    ["text/plain", { "content-type": "text/plain" }],
    ["a missing content-type", {}],
  ])("answers 502 instead of relaying %s from the engine", async (_label, headers) => {
    upstream.engineFetch.mockResolvedValueOnce(new Response("<html>internal</html>", { status: 200, headers }));
    const res = await call(["health"]);
    expect(res.status).toBe(502);
    const body = await res.text();
    expect(JSON.parse(body)).toMatchObject({ error: "engine_unreachable" });
    expect(body).not.toContain("<html>");
  });
});

describe("GET /api/engine/[...path] failures", () => {
  it("answers 502 engine_unreachable when the engine is down", async () => {
    upstream.engineFetch.mockRejectedValueOnce(new TypeError("fetch failed"));
    const res = await call(["health"]);
    expect(res.status).toBe(502);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.json()).toEqual({ error: "engine_unreachable", message: "The Open Books engine is temporarily unavailable." });
  });

  it("does not leak the upstream address or error detail in the 502 body", async () => {
    upstream.engineFetch.mockRejectedValueOnce(
      Object.assign(new TypeError("fetch failed"), { cause: { code: "ECONNREFUSED", address: "127.0.0.1", port: 8765 } }),
    );
    const body = await (await call(["health"])).text();
    expect(body).not.toContain("127.0.0.1");
    expect(body).not.toContain("8765");
    expect(body).not.toContain("ECONNREFUSED");
    expect(body).not.toContain("stack");
  });

  it("forwards the caller's abort signal to the engine", async () => {
    const controller = new AbortController();
    upstream.engineFetch.mockResolvedValueOnce(engineReply("{}"));
    await call(["health"], { signal: controller.signal });
    const init = upstream.engineFetch.mock.calls[0]?.[1] as RequestInit;
    expect(init.signal).toBeDefined();
    expect(init.cache).toBe("no-store");
  });

  it("answers 502 when the caller aborts mid-request", async () => {
    const controller = new AbortController();
    upstream.engineFetch.mockImplementationOnce(async () => {
      controller.abort();
      throw new DOMException("The operation was aborted.", "AbortError");
    });
    const res = await call(["health"], { signal: controller.signal });
    expect(res.status).toBe(502);
  });

  it("answers 502 when the engine accepts the connection and then fails", async () => {
    upstream.engineFetch.mockRejectedValueOnce(new Error("socket hang up"));
    expect((await call(["formats"])).status).toBe(502);
  });
});

describe("/api/engine/[...path] methods", () => {
  it("exports only GET, so POST and other methods are answered 405 by Next", () => {
    expect(Object.keys(engineRoute).filter((k) => /^[A-Z]+$/.test(k))).toEqual(["GET"]);
  });
});
