const SECRET_PATTERNS: readonly RegExp[] = [
  /(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}/,
  /AIza[0-9A-Za-z_-]{20,}/,
  /(?<![A-Za-z0-9])xai-[A-Za-z0-9]{16,}/,
  /Bearer\s+\S{16,}/i,
  /[A-Za-z0-9_-]{40,}/,
];

export function looksLikeSecret(text: string): boolean {
  return SECRET_PATTERNS.some((pattern) => pattern.test(text));
}

export function containsSecretLikeText(value: unknown): boolean {
  const pending: unknown[] = [value];
  while (pending.length > 0) {
    const current = pending.pop();
    if (typeof current === "string") {
      if (looksLikeSecret(current)) return true;
    } else if (Array.isArray(current)) {
      pending.push(...current);
    } else if (current !== null && typeof current === "object") {
      for (const [key, child] of Object.entries(current)) {
        if (looksLikeSecret(key)) return true;
        pending.push(child);
      }
    }
  }
  return false;
}
