type TakeResult = { allowed: boolean; retryAfterSec: number };

type TokenBucketOptions = {
  capacity: number;
  refillPerSec: number;
  now?: () => number;
  maxKeys?: number;
};

type TokenBucket = {
  take: (key: string) => TakeResult;
};

type BucketState = { tokens: number; updatedAt: number };

const DEFAULT_MAX_KEYS = 5000;

export function createTokenBucket({
  capacity,
  refillPerSec,
  now = Date.now,
  maxKeys = DEFAULT_MAX_KEYS,
}: TokenBucketOptions): TokenBucket {
  // Map preserves insertion order; re-inserting on every take keeps the
  // first key as the least recently used one, which is the eviction victim.
  // ponytail: in-memory per instance; serverless instances do not share buckets.
  const buckets = new Map<string, BucketState>();

  function evictOverflow(): void {
    while (buckets.size > maxKeys) {
      const oldest = buckets.keys().next();
      if (oldest.done) return;
      buckets.delete(oldest.value);
    }
  }

  return {
    take(key) {
      const current = now();
      const previous = buckets.get(key) ?? { tokens: capacity, updatedAt: current };
      const elapsedSec = Math.max(0, (current - previous.updatedAt) / 1000);
      const available = Math.min(capacity, previous.tokens + elapsedSec * refillPerSec);

      const allowed = available >= 1;
      const tokens = allowed ? available - 1 : available;
      const retryAfterSec = allowed ? 0 : Math.ceil((1 - available) / refillPerSec);

      buckets.delete(key);
      buckets.set(key, { tokens, updatedAt: current });
      evictOverflow();

      return { allowed, retryAfterSec };
    },
  };
}
