export const DEFAULT_NEXT_PATH = "/app";

const PLACEHOLDER_ORIGIN = "http://openbooks.invalid";
const UNSAFE = /[\\\x00-\x1f\x7f]/;

function isSafe(value: string): boolean {
  if (!value.startsWith("/") || value.startsWith("//") || UNSAFE.test(value)) return false;
  try {
    return new URL(value, PLACEHOLDER_ORIGIN).origin === PLACEHOLDER_ORIGIN;
  } catch {
    return false;
  }
}

export function safeNextPath(raw: string | string[] | null | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value || !isSafe(value)) return DEFAULT_NEXT_PATH;
  let decoded: string;
  try {
    decoded = decodeURIComponent(value);
  } catch {
    return DEFAULT_NEXT_PATH;
  }
  return isSafe(decoded) ? value : DEFAULT_NEXT_PATH;
}

export function signInUrlFor(pathname: string, search: string): string {
  const target = safeNextPath(`${pathname}${search}`);
  return `/auth/sign-in?next=${encodeURIComponent(target)}`;
}
