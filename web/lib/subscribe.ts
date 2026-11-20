export type ParseSubscribeResult =
  | { ok: true; email: string }
  | { ok: false; reason: "invalid" | "spam" };

const MIN_EMAIL_LENGTH = 3;
const MAX_EMAIL_LENGTH = 254;
const MAX_LOCAL_PART_LENGTH = 64;
// Whitespace (incl. spaces) and ASCII control characters.
const FORBIDDEN_CHARS = /[\s\u0000-\u001f\u007f]/;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isValidEmail(email: string): boolean {
  if (email.length < MIN_EMAIL_LENGTH || email.length > MAX_EMAIL_LENGTH) return false;
  if (FORBIDDEN_CHARS.test(email)) return false;

  const parts = email.split("@");
  if (parts.length !== 2) return false;

  const [localPart, domain] = parts as [string, string];
  if (localPart.length === 0 || localPart.length > MAX_LOCAL_PART_LENGTH) return false;
  if (!domain.includes(".")) return false;

  return domain.split(".").every((label) => label.length > 0);
}

export function parseSubscribe(body: unknown): ParseSubscribeResult {
  if (!isObject(body)) return { ok: false, reason: "invalid" };

  const { email, website } = body;
  if (website !== undefined && typeof website !== "string") {
    return { ok: false, reason: "invalid" };
  }
  if (typeof website === "string" && website.trim() !== "") {
    return { ok: false, reason: "spam" };
  }

  if (typeof email !== "string") return { ok: false, reason: "invalid" };

  const normalised = email.trim().toLowerCase();
  if (!isValidEmail(normalised)) return { ok: false, reason: "invalid" };

  return { ok: true, email: normalised };
}
