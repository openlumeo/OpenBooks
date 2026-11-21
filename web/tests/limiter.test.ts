import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const neonMock = vi.hoisted(() => ({ neon: vi.fn() }));
vi.mock("@neondatabase/serverless", () => neonMock);

import { clientKey, limitOr429, takeShared } from "@/lib/server/limiter";

function request(headers: Record<string, string> = {}): Request {
  return new Request("http://localhost/api/x", { method: "POST", headers });
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("clientKey", () => {
  it("uses the last x-forwarded-for entry the proxy appended, not caller-supplied ones", () => {
    expect(clientKey(request({ "x-forwarded-for": "9.9.9.9, 203.0.113.7" }))).toBe("203.0.113.7");
  });
  it("ignores spoofed entries that precede the proxy-added address", () => {
    expect(clientKey(request({ "x-forwarded-for": "1.1.1.1, 2.2.2.2, 198.51.100.9" }))).toBe("198.51.100.9");
  });
  it("returns unknown when no forwarding header is present", () => {
    expect(clientKey(request())).toBe("unknown");
  });
  it("uses the Netlify client IP header on Netlify, trimmed", () => {
    vi.stubEnv("NETLIFY", "true");
    expect(clientKey(request({ "x-nf-client-connection-ip": " 198.51.100.4 " }))).toBe("198.51.100.4");
  });
  it("returns unknown on Netlify when the client IP header is missing", () => {
    vi.stubEnv("NETLIFY", "true");
    expect(clientKey(request({ "x-forwarded-for": "203.0.113.7" }))).toBe("unknown");
  });
});

describe("takeShared without a database", () => {
  it("uses a local bucket in development and reports retry-after", async () => {
    vi.stubEnv("DATABASE_URL", "");
    const limit = { capacity: 1, refillPerSec: 1 / 60 };
    expect((await takeShared("dev-local", "k1", limit)).allowed).toBe(true);
    expect(await takeShared("dev-local", "k1", limit)).toEqual({ allowed: false, retryAfterSec: 60 });
  });

  it("refuses to start in production without a shared database", async () => {
    vi.stubEnv("DATABASE_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    await expect(takeShared("prod", "k", { capacity: 1, refillPerSec: 1 })).rejects.toThrow(
      "Rate limiter database is not configured",
    );
  });

  it("answers 503 from limitOr429 when production has no database", async () => {
    vi.stubEnv("DATABASE_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    const res = await limitOr429(request({ "x-forwarded-for": "203.0.113.50" }), "runs");
    expect(res?.status).toBe(503);
    expect(await res?.json()).toEqual({ error: "limiter_unavailable", message: "Please try again shortly." });
  });
});

describe("takeShared with a database", () => {
  it("returns the verdict from the atomic take_token call", async () => {
    vi.stubEnv("DATABASE_URL", "postgres://example.invalid/db");
    const sql = vi.fn(async () => [{ allowed: false, retry_after_sec: 7 }]);
    neonMock.neon.mockReturnValue(sql);
    const verdict = await takeShared("route", "ip", { capacity: 10, refillPerSec: 0.05 });
    expect(verdict).toEqual({ allowed: false, retryAfterSec: 7 });
    expect(sql.mock.calls[0]?.slice(1)).toEqual(["route:ip", 10, 0.05]);
  });

  it("falls back to the local bucket in development when the database fails", async () => {
    vi.stubEnv("DATABASE_URL", "postgres://example.invalid/db");
    vi.stubEnv("NODE_ENV", "development");
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    neonMock.neon.mockImplementation(() => {
      throw new Error("db down");
    });
    expect((await takeShared("db-dev-fallback", "k", { capacity: 1, refillPerSec: 1 })).allowed).toBe(true);
  });

  it("rethrows database failures in production", async () => {
    vi.stubEnv("DATABASE_URL", "postgres://example.invalid/db");
    vi.stubEnv("NODE_ENV", "production");
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    neonMock.neon.mockImplementation(() => {
      throw new Error("db down");
    });
    await expect(takeShared("prod-db", "k", { capacity: 1, refillPerSec: 1 })).rejects.toThrow("db down");
  });
});

describe("limitOr429", () => {
  it("lets a request through while the bucket has tokens", async () => {
    vi.stubEnv("DATABASE_URL", "");
    expect(await limitOr429(request({ "x-forwarded-for": "198.51.100.20" }), "link")).toBeNull();
  });

  it("answers 429 with retry-after once a client exhausts the bucket", async () => {
    vi.stubEnv("DATABASE_URL", "");
    const headers = { "x-forwarded-for": "198.51.100.30" };
    for (let i = 0; i < 10; i += 1) expect(await limitOr429(request(headers), "runs")).toBeNull();
    const res = await limitOr429(request(headers), "runs");
    expect(res?.status).toBe(429);
    expect(Number(res?.headers.get("retry-after"))).toBeGreaterThan(0);
    expect(await res?.json()).toMatchObject({ error: "rate_limited" });
  });

  it("limits each client separately", async () => {
    vi.stubEnv("DATABASE_URL", "");
    for (let i = 0; i < 10; i += 1) await limitOr429(request({ "x-forwarded-for": "198.51.100.40" }), "runs");
    expect(await limitOr429(request({ "x-forwarded-for": "198.51.100.41" }), "runs")).toBeNull();
  });
});
