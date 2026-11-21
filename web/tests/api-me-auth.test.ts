import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const auth = vi.hoisted(() => ({
  getSession: vi.fn(),
  handler: vi.fn(),
  handlers: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn(), PATCH: vi.fn() },
}));
vi.mock("@/lib/auth/server", () => ({
  getAuth: () => ({ getSession: auth.getSession, handler: auth.handler }),
}));

import * as meRoute from "@/app/api/me/route";
const meGet = meRoute.GET;
import * as authRoute from "@/app/api/auth/[...path]/route";

beforeEach(() => {
  auth.getSession.mockReset();
  auth.handler.mockReset();
  auth.handler.mockReturnValue(auth.handlers);
  for (const fn of Object.values(auth.handlers)) fn.mockReset();
});

describe("GET /api/me", () => {
  it("returns id, email and name for a signed-in user", async () => {
    auth.getSession.mockResolvedValueOnce({ data: { user: { id: "u1", email: "ada@example.com", name: "Ada" } } });
    const res = await meGet();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ id: "u1", email: "ada@example.com", name: "Ada" });
  });

  it("leaves session fields other than id, email and name out of the response", async () => {
    auth.getSession.mockResolvedValueOnce({
      data: { user: { id: "u1", email: "ada@example.com", name: "Ada", role: "admin", image: "x" }, session: { token: "secret-session-token" } },
    });
    const body = await (await meGet()).text();
    expect(body).not.toContain("secret-session-token");
    expect(body).not.toContain("admin");
    expect(JSON.parse(body)).toEqual({ id: "u1", email: "ada@example.com", name: "Ada" });
  });

  it("answers 401 Unauthorized when there is no session", async () => {
    auth.getSession.mockResolvedValueOnce({ data: null });
    const res = await meGet();
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: "Unauthorized" });
  });

  it("answers 401 when the session carries no user", async () => {
    auth.getSession.mockResolvedValueOnce({ data: { session: { token: "t" } } });
    expect((await meGet()).status).toBe(401);
  });

  it("exports only GET, so other methods are answered 405 by Next", () => {
    expect(Object.keys(meRoute).filter((k) => /^[A-Z]+$/.test(k))).toEqual(["GET"]);
  });

  it("marks the identity response no-store so a shared cache never keeps it", async () => {
    auth.getSession.mockResolvedValueOnce({ data: { user: { id: "u1", email: "a@b.co", name: "Ada" } } });
    const res = await meGet();
    expect(res.headers.get("cache-control")).toBe("no-store");
  });
});

describe("/api/auth/[...path]", () => {
  it("exports exactly the five Neon Auth methods, so HEAD and OPTIONS are not routed", () => {
    expect(Object.keys(authRoute).filter((k) => /^[A-Z]+$/.test(k)).sort()).toEqual(["DELETE", "GET", "PATCH", "POST", "PUT"]);
  });

  it.each(["GET", "POST", "PUT", "DELETE", "PATCH"] as const)("delegates %s to the Neon Auth handler with the request and context", async (method) => {
    const response = new Response("ok", { status: 200 });
    auth.handlers[method].mockResolvedValueOnce(response);
    const req = new Request("http://localhost/api/auth/sign-in", { method });
    const ctx = { params: Promise.resolve({ path: ["sign-in"] }) };

    const res = await authRoute[method](req, ctx);

    expect(res).toBe(response);
    expect(auth.handlers[method]).toHaveBeenCalledWith(req, ctx);
  });

  it("passes the Neon Auth 401 for an unauthenticated session call through unchanged", async () => {
    auth.handlers.GET.mockResolvedValueOnce(Response.json({ error: "UNAUTHORIZED" }, { status: 401 }));
    const res = await authRoute.GET(new Request("http://localhost/api/auth/get-session"), {
      params: Promise.resolve({ path: ["get-session"] }),
    });
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: "UNAUTHORIZED" });
  });
});
