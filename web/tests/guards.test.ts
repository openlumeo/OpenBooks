import { describe, expect, it } from "vitest";
import { createRateLimiter, rejectOversize } from "@/lib/guards";

function req(headers: Record<string, string>): Request {
  return new Request("http://localhost/api/x", { method: "POST", headers });
}

describe("rejectOversize", () => {
  it("lets a request within the limit through", () => {
    expect(rejectOversize(req({ "content-length": "100" }), 1000)).toBeNull();
  });
  it("rejects a request over the limit with 413", async () => {
    const res = rejectOversize(req({ "content-length": "1001" }), 1000);
    expect(res?.status).toBe(413);
    expect(await res?.json()).toMatchObject({ error: "too_large" });
  });
  it("rejects a missing or malformed length with 411", () => {
    expect(rejectOversize(req({}), 1000)?.status).toBe(411);
    expect(rejectOversize(req({ "content-length": "abc" }), 1000)?.status).toBe(411);
    expect(rejectOversize(req({ "content-length": "-5" }), 1000)?.status).toBe(411);
  });
});

describe("createRateLimiter", () => {
  it("allows up to max calls per window and then limits", () => {
    const t = 0;
    const limited = createRateLimiter(3, 1000, () => t);
    expect([limited(), limited(), limited(), limited()]).toEqual([false, false, false, true]);
  });
  it("starts a fresh window once the window has passed", () => {
    let t = 0;
    const limited = createRateLimiter(1, 1000, () => t);
    expect([limited(), limited()]).toEqual([false, true]);
    t = 1000;
    expect(limited()).toBe(false);
  });
});
