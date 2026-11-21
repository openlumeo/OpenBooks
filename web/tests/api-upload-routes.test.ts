import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const limiter = vi.hoisted(() => ({ limitOr429: vi.fn() }));
vi.mock("@/lib/server/limiter", () => limiter);

import { POST as runsPost } from "@/app/api/runs/route";
import { POST as rolesPost } from "@/app/api/roles/route";
import { POST as linkPost } from "@/app/api/link/route";

const MULTIPART = "multipart/form-data; boundary=test";
const fetchMock = vi.fn<(url: string, init: RequestInit) => Promise<Response>>();

function connectionError(code: string): TypeError {
  return Object.assign(new TypeError("fetch failed"), { cause: { code } });
}

function upload(path: string, options: { contentType?: string; contentLength?: string; signal?: AbortSignal } = {}): Request {
  const headers: Record<string, string> = { "content-type": options.contentType ?? MULTIPART };
  if (options.contentLength !== undefined) headers["content-length"] = options.contentLength;
  return new Request(`http://localhost${path}`, { method: "POST", headers, body: "--test--", signal: options.signal });
}

beforeEach(() => {
  fetchMock.mockReset();
  limiter.limitOr429.mockReset();
  limiter.limitOr429.mockResolvedValue(null);
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("POST /api/runs", () => {
  it("answers 429 when the limiter refuses the caller", async () => {
    limiter.limitOr429.mockResolvedValueOnce(Response.json({ error: "rate_limited" }, { status: 429 }));
    const res = await runsPost(upload("/api/runs", { contentLength: "10" }));
    expect(res.status).toBe(429);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers 415 for a non-multipart body", async () => {
    const res = await runsPost(upload("/api/runs", { contentType: "application/json", contentLength: "10" }));
    expect(res.status).toBe(415);
    expect(await res.json()).toMatchObject({ error: "bad_request" });
  });

  it("answers 411 when the upload has no Content-Length", async () => {
    expect((await runsPost(upload("/api/runs"))).status).toBe(411);
  });

  it("answers 413 when the upload exceeds the 100 MB cap", async () => {
    const res = await runsPost(upload("/api/runs", { contentLength: String(100 * 1024 * 1024 + 1) }));
    expect(res.status).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers 502 when the engine is unreachable", async () => {
    fetchMock.mockRejectedValueOnce(connectionError("UND_ERR_SOCKET"));
    const res = await runsPost(upload("/api/runs", { contentLength: "10" }));
    expect(res.status).toBe(502);
    expect(await res.json()).toMatchObject({ error: "engine_unreachable" });
  });

  it("answers 499 when the caller aborts", async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));
    const res = await runsPost(upload("/api/runs", { contentLength: "10", signal: controller.signal }));
    expect(res.status).toBe(499);
  });

  it("relays the engine event stream for a valid upload", async () => {
    fetchMock.mockResolvedValueOnce(new Response("data: {}\n\n", { headers: { "content-type": "text/event-stream" } }));
    const res = await runsPost(upload("/api/runs", { contentLength: "10" }));
    expect(res.status).toBe(200);
    expect(res.headers.get("x-accel-buffering")).toBe("no");
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(fetchMock.mock.calls[0]?.[0]).toMatch(/\/v1\/runs$/);
    expect(limiter.limitOr429).toHaveBeenCalledWith(expect.any(Request), "runs");
  });
});

describe("POST /api/roles", () => {
  it("answers 415 for a non-multipart body", async () => {
    const res = await rolesPost(upload("/api/roles", { contentType: "text/plain", contentLength: "10" }));
    expect(res.status).toBe(415);
  });

  it("answers 413 above the 25 MB per-file cap", async () => {
    const res = await rolesPost(upload("/api/roles", { contentLength: String(25 * 1024 * 1024 + 1) }));
    expect(res.status).toBe(413);
  });

  it("answers 502 when the engine is unreachable", async () => {
    fetchMock.mockRejectedValueOnce(connectionError("UND_ERR_SOCKET"));
    expect((await rolesPost(upload("/api/roles", { contentLength: "10" }))).status).toBe(502);
  });

  it("answers 499 when the caller aborts", async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));
    expect((await rolesPost(upload("/api/roles", { contentLength: "10", signal: controller.signal }))).status).toBe(499);
  });

  it("relays the engine JSON for a valid upload", async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ roles: [] }));
    const res = await rolesPost(upload("/api/roles", { contentLength: "10" }));
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.json()).toEqual({ roles: [] });
  });
});

describe("POST /api/link", () => {
  function json(body: string, contentLength?: string): Request {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (contentLength !== undefined) headers["content-length"] = contentLength;
    return new Request("http://localhost/api/link", { method: "POST", headers, body });
  }

  it("answers 429 when the limiter refuses the caller", async () => {
    limiter.limitOr429.mockResolvedValueOnce(Response.json({ error: "rate_limited" }, { status: 429 }));
    expect((await linkPost(json("{}", "2"))).status).toBe(429);
  });

  it("answers 411 when the body has no Content-Length", async () => {
    expect((await linkPost(json("{}"))).status).toBe(411);
  });

  it("answers 413 above the 4 MB JSON cap", async () => {
    expect((await linkPost(json("{}", String(4 * 1024 * 1024 + 1)))).status).toBe(413);
  });

  it("answers 502 when the engine is unreachable", async () => {
    fetchMock.mockRejectedValueOnce(connectionError("UND_ERR_SOCKET"));
    const res = await linkPost(json('{"code":"x"}', "12"));
    expect(res.status).toBe(502);
    expect(await res.json()).toMatchObject({ error: "engine_unreachable" });
  });

  it("forwards the JSON body to the engine and relays the answer", async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ linked: true }));
    const res = await linkPost(json('{"code":"x"}', "12"));
    expect(res.status).toBe(200);
    expect(fetchMock.mock.calls[0]?.[0]).toMatch(/\/v1\/link$/);
    expect(fetchMock.mock.calls[0]?.[1].body).toBe('{"code":"x"}');
    expect(await res.json()).toEqual({ linked: true });
  });
});
