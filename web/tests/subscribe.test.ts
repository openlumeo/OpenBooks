import { describe, expect, it } from "vitest";
import { parseSubscribe } from "../lib/subscribe";
import { createTokenBucket } from "../lib/token-bucket";

describe("parseSubscribe", () => {
  it("accepts a valid email", () => {
    expect(parseSubscribe({ email: "reader@example.com" })).toEqual({
      ok: true,
      email: "reader@example.com",
    });
  });

  it("normalises uppercase to lowercase", () => {
    expect(parseSubscribe({ email: "Reader@Example.COM" })).toEqual({
      ok: true,
      email: "reader@example.com",
    });
  });

  it("trims surrounding spaces", () => {
    expect(parseSubscribe({ email: "  reader@example.com  " })).toEqual({
      ok: true,
      email: "reader@example.com",
    });
  });

  it("rejects internal whitespace", () => {
    expect(parseSubscribe({ email: "read er@example.com" })).toEqual({
      ok: false,
      reason: "invalid",
    });
  });

  it("rejects a missing @", () => {
    expect(parseSubscribe({ email: "reader.example.com" })).toEqual({
      ok: false,
      reason: "invalid",
    });
  });

  it("rejects emails longer than 254 characters", () => {
    const local = "a".repeat(60);
    const domain = `${"b".repeat(60)}.${"c".repeat(60)}.${"d".repeat(80)}.com`;
    const email = `${local}@${domain}`;
    expect(email.length).toBeGreaterThan(254);
    expect(parseSubscribe({ email })).toEqual({ ok: false, reason: "invalid" });
  });

  it("rejects a local part longer than 64 characters", () => {
    const email = `${"a".repeat(65)}@example.com`;
    expect(parseSubscribe({ email })).toEqual({ ok: false, reason: "invalid" });
  });

  it("rejects a domain without a dot", () => {
    expect(parseSubscribe({ email: "reader@localhost" })).toEqual({
      ok: false,
      reason: "invalid",
    });
  });

  it("returns spam when the honeypot is filled", () => {
    expect(parseSubscribe({ email: "reader@example.com", website: "http://bot.test" })).toEqual({
      ok: false,
      reason: "spam",
    });
  });

  it("treats an empty honeypot as absent", () => {
    expect(parseSubscribe({ email: "reader@example.com", website: "" })).toEqual({
      ok: true,
      email: "reader@example.com",
    });
  });

  it("rejects non-object bodies", () => {
    expect(parseSubscribe(null)).toEqual({ ok: false, reason: "invalid" });
    expect(parseSubscribe("reader@example.com")).toEqual({ ok: false, reason: "invalid" });
    expect(parseSubscribe(["reader@example.com"])).toEqual({ ok: false, reason: "invalid" });
  });

  it("rejects a non-string email", () => {
    expect(parseSubscribe({ email: 42 })).toEqual({ ok: false, reason: "invalid" });
    expect(parseSubscribe({})).toEqual({ ok: false, reason: "invalid" });
  });
});

describe("createTokenBucket", () => {
  function makeClock(startMs: number): { now: () => number; advanceMs: (ms: number) => void } {
    let current = startMs;
    return {
      now: () => current,
      advanceMs: (ms: number) => {
        current += ms;
      },
    };
  }

  it("allows a burst up to capacity then denies with a positive retryAfterSec", () => {
    const clock = makeClock(0);
    const bucket = createTokenBucket({ capacity: 3, refillPerSec: 1, now: clock.now });

    expect(bucket.take("ip")).toEqual({ allowed: true, retryAfterSec: 0 });
    expect(bucket.take("ip")).toEqual({ allowed: true, retryAfterSec: 0 });
    expect(bucket.take("ip")).toEqual({ allowed: true, retryAfterSec: 0 });

    const denied = bucket.take("ip");
    expect(denied.allowed).toBe(false);
    expect(denied.retryAfterSec).toBeGreaterThan(0);
  });

  it("refills tokens over fake time", () => {
    const clock = makeClock(0);
    const bucket = createTokenBucket({ capacity: 1, refillPerSec: 1, now: clock.now });

    expect(bucket.take("ip").allowed).toBe(true);
    expect(bucket.take("ip").allowed).toBe(false);

    clock.advanceMs(999);
    expect(bucket.take("ip").allowed).toBe(false);

    clock.advanceMs(1000);
    expect(bucket.take("ip").allowed).toBe(true);
  });

  it("keeps separate keys independent", () => {
    const clock = makeClock(0);
    const bucket = createTokenBucket({ capacity: 1, refillPerSec: 0.001, now: clock.now });

    expect(bucket.take("a").allowed).toBe(true);
    expect(bucket.take("a").allowed).toBe(false);
    expect(bucket.take("b").allowed).toBe(true);
  });

  it("evicts the oldest keys beyond maxKeys", () => {
    const clock = makeClock(0);
    const bucket = createTokenBucket({
      capacity: 1,
      refillPerSec: 0.001,
      now: clock.now,
      maxKeys: 2,
    });

    expect(bucket.take("a").allowed).toBe(true);
    expect(bucket.take("b").allowed).toBe(true);
    expect(bucket.take("c").allowed).toBe(true);

    expect(bucket.take("a").allowed).toBe(true);
    expect(bucket.take("c").allowed).toBe(false);
  });
});
