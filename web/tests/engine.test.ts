import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { engineDown, engineFetch, proxyUpload, relay } from "@/lib/server/engine";

const fetchMock = vi.fn<(url: string, init: RequestInit) => Promise<Response>>();

function connectionError(code: string): TypeError {
  return Object.assign(new TypeError("fetch failed"), { cause: { code } });
}

function ok(headers: Record<string, string> = { "content-type": "application/json" }, status = 200): Response {
  return new Response("{}", { status, headers });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("engineFetch request headers", () => {
  it("forwards the caller's x-request-id unchanged", async () => {
    fetchMock.mockResolvedValueOnce(ok());
    await engineFetch("/v1/link", { headers: { "x-request-id": "req-123" } });
    expect(new Headers(fetchMock.mock.calls[0]?.[1].headers).get("x-request-id")).toBe("req-123");
  });

  it("generates a request id when the caller sends none", async () => {
    fetchMock.mockResolvedValueOnce(ok());
    await engineFetch("/v1/link");
    expect(new Headers(fetchMock.mock.calls[0]?.[1].headers).get("x-request-id")).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("sends the engine key and refuses redirects", async () => {
    vi.resetModules();
    vi.stubEnv("OPENBOOKS_ENGINE_KEY", "tunnel-key");
    const fresh = await import("@/lib/server/engine");
    fetchMock.mockResolvedValueOnce(ok());
    await fresh.engineFetch("/v1/link");
    const init = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get("x-openbooks-key")).toBe("tunnel-key");
    expect(init?.redirect).toBe("error");
  });
});

describe("engineFetch retries", () => {
  it("retries a connection-setup failure and then succeeds", async () => {
    vi.useFakeTimers();
    fetchMock.mockRejectedValueOnce(connectionError("ECONNREFUSED")).mockResolvedValueOnce(ok());
    const pending = engineFetch("/v1/link");
    await vi.advanceTimersByTimeAsync(250);
    expect((await pending).status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after the retry budget and rethrows the last error", async () => {
    vi.useFakeTimers();
    fetchMock.mockRejectedValue(connectionError("ECONNREFUSED"));
    const pending = engineFetch("/v1/link").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toBeInstanceOf(TypeError);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not retry a failure that may have happened after the request was sent", async () => {
    fetchMock.mockRejectedValueOnce(connectionError("UND_ERR_SOCKET"));
    await expect(engineFetch("/v1/link")).rejects.toThrow("fetch failed");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a streamed body, which cannot be replayed", async () => {
    fetchMock.mockRejectedValueOnce(connectionError("ECONNREFUSED"));
    const body = new ReadableStream<Uint8Array>();
    await expect(engineFetch("/v1/runs", { method: "POST", body })).rejects.toThrow("fetch failed");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry once the caller has aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(connectionError("ECONNREFUSED"));
    await expect(engineFetch("/v1/link", { signal: controller.signal })).rejects.toThrow("fetch failed");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("relay", () => {
  it("passes JSON and event-stream bodies through with the upstream status", () => {
    const res = relay(ok({ "content-type": "application/json" }, 201));
    expect(res.status).toBe(201);
    expect(res.headers.get("content-type")).toBe("application/json");
  });

  it("copies only allow-listed headers and applies the extra headers", () => {
    const res = relay(
      ok({
        "content-type": "application/json",
        "retry-after": "3",
        "x-request-id": "r1",
        "x-secret": "do-not-forward",
      }),
      { "cache-control": "no-store" },
    );
    expect(res.headers.get("retry-after")).toBe("3");
    expect(res.headers.get("x-request-id")).toBe("r1");
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(res.headers.get("x-secret")).toBeNull();
  });

  it("accepts media types with parameters, ignoring case", () => {
    expect(relay(ok({ "content-type": "Application/JSON; charset=utf-8" })).status).toBe(200);
  });

  it("replaces a body with an unlisted media type by engine_unreachable", async () => {
    const res = relay(ok({ "content-type": "text/html" }));
    expect(res.status).toBe(502);
    expect(await res.json()).toMatchObject({ error: "engine_unreachable" });
  });

  it("treats a body with no content type as unreachable", () => {
    const upstream = new Response(new ReadableStream<Uint8Array>());
    expect(relay(upstream).status).toBe(502);
  });

  it("passes a body-less upstream through even without a content type", () => {
    expect(relay(new Response(null, { status: 204 })).status).toBe(204);
  });
});

describe("engineDown", () => {
  it("answers 502 with the shared error envelope and no caching", async () => {
    const res = engineDown();
    expect(res.status).toBe(502);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.json()).toEqual({
      error: "engine_unreachable",
      message: "The Open Books engine is temporarily unavailable.",
    });
  });
});

describe("proxyUpload", () => {
  function upload(signal?: AbortSignal): Request {
    return new Request("http://localhost/api/runs", {
      method: "POST",
      headers: { "content-type": "multipart/form-data; boundary=test" },
      body: "--test--",
      signal,
    });
  }

  it("streams the upload with its content type and relays the engine response", async () => {
    fetchMock.mockResolvedValueOnce(ok({ "content-type": "text/event-stream" }));
    const res = await proxyUpload(upload(), "/v1/runs", { "x-accel-buffering": "no" });
    expect(res.status).toBe(200);
    expect(res.headers.get("x-accel-buffering")).toBe("no");
    expect(new Headers(fetchMock.mock.calls[0]?.[1].headers).get("content-type")).toBe("multipart/form-data; boundary=test");
  });

  it("answers 499 when the caller aborted during the upload", async () => {
    const controller = new AbortController();
    controller.abort();
    fetchMock.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));
    const res = await proxyUpload(upload(controller.signal), "/v1/runs", {});
    expect(res.status).toBe(499);
  });

  it("answers 502 when the engine is unreachable and the caller is still connected", async () => {
    fetchMock.mockRejectedValueOnce(connectionError("UND_ERR_SOCKET"));
    const res = await proxyUpload(upload(), "/v1/runs", {});
    expect(res.status).toBe(502);
  });
});
