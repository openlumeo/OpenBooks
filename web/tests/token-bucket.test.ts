import { describe, expect, it } from "vitest";
import { createTokenBucket } from "@/lib/token-bucket";

function manualClock(start = 0) {
  let time = start;
  return {
    now: () => time,
    advance: (ms: number) => {
      time += ms;
    },
    set: (ms: number) => {
      time = ms;
    },
  };
}

describe("createTokenBucket", () => {
  it("allows a burst up to capacity and then refuses", () => {
    const bucket = createTokenBucket({ capacity: 2, refillPerSec: 1, now: manualClock().now });
    expect([bucket.take("a").allowed, bucket.take("a").allowed, bucket.take("a").allowed]).toEqual([true, true, false]);
  });

  it("reports retry-after in whole seconds until the next token", () => {
    const bucket = createTokenBucket({ capacity: 1, refillPerSec: 0.5, now: manualClock().now });
    bucket.take("a");
    expect(bucket.take("a")).toEqual({ allowed: false, retryAfterSec: 2 });
  });

  it("refills with elapsed time and never beyond capacity", () => {
    const clock = manualClock();
    const bucket = createTokenBucket({ capacity: 2, refillPerSec: 1, now: clock.now });
    bucket.take("a");
    bucket.take("a");
    clock.advance(1000);
    expect(bucket.take("a").allowed).toBe(true);
    expect(bucket.take("a").allowed).toBe(false);
    clock.advance(10_000);
    expect([bucket.take("a").allowed, bucket.take("a").allowed, bucket.take("a").allowed]).toEqual([true, true, false]);
  });

  it("keeps keys independent", () => {
    const bucket = createTokenBucket({ capacity: 1, refillPerSec: 1, now: manualClock().now });
    expect(bucket.take("a").allowed).toBe(true);
    expect(bucket.take("a").allowed).toBe(false);
    expect(bucket.take("b").allowed).toBe(true);
  });

  it("treats a clock that goes backwards as no elapsed time", () => {
    const clock = manualClock(1000);
    const bucket = createTokenBucket({ capacity: 1, refillPerSec: 1, now: clock.now });
    expect(bucket.take("a").allowed).toBe(true);
    clock.set(0);
    expect(bucket.take("a").allowed).toBe(false);
  });

  it("evicts the oldest key once maxKeys is exceeded, so it starts full again", () => {
    const bucket = createTokenBucket({ capacity: 1, refillPerSec: 1 / 60, now: manualClock().now, maxKeys: 1 });
    expect(bucket.take("a").allowed).toBe(true);
    expect(bucket.take("b").allowed).toBe(true);
    expect(bucket.take("a").allowed).toBe(true);
  });
});
