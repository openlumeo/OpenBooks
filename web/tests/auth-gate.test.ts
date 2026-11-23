import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/server", () => ({ getAuth: () => ({}) }));

import { config } from "@/proxy";
import { DEFAULT_NEXT_PATH, safeNextPath, signInUrlFor } from "@/lib/auth/next-path";

describe("safeNextPath", () => {
  it.each(["/app", "/app/thread/1", "/app?x=1", "/docs/a#b"])("keeps %s", (p) => {
    expect(safeNextPath(p)).toBe(p);
  });

  it.each([
    "//evil.com",
    "/\\evil.com",
    "\\evil.com",
    "https://evil.com",
    "http://evil.com/app",
    "javascript:alert(1)",
    "evil.com",
    "/%2Fevil.com",
    "/%5Cevil.com",
    "/%2F%2Fevil.com",
    "/app%0d%0aSet-Cookie:x=1",
    "/\tevil.com",
    "/%E0%A4%A",
    "",
    undefined,
    null,
  ])("rejects %s", (p) => {
    expect(safeNextPath(p as string | undefined)).toBe(DEFAULT_NEXT_PATH);
  });

  it("uses the first value of a repeated param", () => {
    expect(safeNextPath(["/app/a", "//evil.com"])).toBe("/app/a");
    expect(safeNextPath(["//evil.com", "/app/a"])).toBe(DEFAULT_NEXT_PATH);
  });
});

describe("signInUrlFor", () => {
  it("encodes the original path and query", () => {
    expect(signInUrlFor("/app/x", "?a=1")).toBe("/auth/sign-in?next=%2Fapp%2Fx%3Fa%3D1");
  });
});

describe("proxy matcher", () => {
  const patterns = config.matcher.map((m) => new RegExp(`^${m.replace(":path*", ".*")}$`));
  const matches = (p: string) => patterns.some((r) => r.test(p));

  it("covers /app and subpaths", () => {
    expect(matches("/app")).toBe(true);
    expect(matches("/app/anything/deep")).toBe(true);
  });

  it.each(["/", "/api/me", "/api/auth/sign-in", "/docs", "/auth/sign-in", "/auth/sign-up", "/llms.txt", "/robots.txt", "/sitemap.xml", "/_next/static/a.js", "/application", "/apple-touch-icon.png"])(
    "skips %s",
    (p) => {
      expect(matches(p)).toBe(false);
    },
  );
});
