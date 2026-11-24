import { unstable_doesMiddlewareMatch } from "next/experimental/testing/server";
import { NextRequest } from "next/server";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

await vi.hoisted(async () => {
  const { AsyncLocalStorage } = await import("node:async_hooks");
  vi.stubGlobal("AsyncLocalStorage", AsyncLocalStorage);
});

vi.mock("@/lib/auth/server", async () => {
  const { createNeonAuth } = await import("@neon/auth/next/server");
  const auth = createNeonAuth({
    baseUrl: "https://auth.example.test",
    cookies: { secret: "test-cookie-signing-secret-for-openbooks" },
  });
  return { getAuth: () => auth };
});

import { config, proxy } from "@/proxy";
import { DEFAULT_NEXT_PATH, safeNextPath, signInUrlFor } from "@/lib/auth/next-path";

afterEach(() => vi.restoreAllMocks());
afterAll(() => vi.unstubAllGlobals());

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
  const matches = (url: string) => unstable_doesMiddlewareMatch({ config, nextConfig: {}, url });

  it("covers /app and subpaths", () => {
    expect(matches("/app")).toBe(true);
    expect(matches("/app/anything/deep")).toBe(true);
  });

  it("also matches OAuth callbacks to public destinations", () => {
    expect(matches("/docs?neon_auth_session_verifier=test")).toBe(true);
  });

  it.each(["/", "/api/me", "/api/auth/sign-in", "/docs", "/auth/sign-in", "/auth/sign-up", "/llms.txt", "/robots.txt", "/sitemap.xml", "/_next/static/a.js", "/application", "/apple-touch-icon.png"])(
    "skips %s",
    (p) => {
      expect(matches(p)).toBe(false);
    },
  );
});

describe("workspace authentication", () => {
  const origin = "https://openbooks.example.test";

  it("preserves the requested workspace URL when sending a signed-out user to sign-in", async () => {
    const response = await proxy(new NextRequest(`${origin}/app?view=activity`));

    expect(response.headers.get("location")).toBe(
      `${origin}/auth/sign-in?next=%2Fapp%3Fview%3Dactivity`,
    );
  });

  it("exchanges a Google callback and redirects to the workspace with a session cookie", async () => {
    const sessionCookie = "__Secure-neon-auth.session_token=test-session";
    const now = new Date().toISOString();
    const expiresAt = new Date(Date.now() + 3600_000).toISOString();
    const fetchAuth = vi.spyOn(globalThis, "fetch").mockImplementation(async () => Response.json(
      {
        session: { token: "test-session", createdAt: now, updatedAt: now, expiresAt },
        user: { id: "test-user", createdAt: now, updatedAt: now },
      },
      { headers: { "set-cookie": `${sessionCookie}; Path=/; Secure; HttpOnly` } },
    ));
    const response = await proxy(new NextRequest(
      `${origin}/app?view=activity&neon_auth_session_verifier=test-verifier`,
      { headers: { cookie: "__Secure-neon-auth.session_challenge=test-challenge" } },
    ));

    expect(new URL(String(fetchAuth.mock.calls[0]?.[0])).searchParams.get("neon_auth_session_verifier"))
      .toBe("test-verifier");
    expect(response.headers.get("location")).toBe(`${origin}/app?view=activity`);
    expect(response.headers.getSetCookie()).toEqual(
      expect.arrayContaining([expect.stringContaining(sessionCookie)]),
    );

    const workspace = await proxy(new NextRequest(`${origin}/app?view=activity`, {
      headers: { cookie: sessionCookie },
    }));
    expect(workspace.headers.get("location")).toBeNull();
  });
});
