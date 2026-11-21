export const NO_STORE_HEADERS = { "cache-control": "no-store" } as const;

/** The shared error envelope: { error, message }. */
export function jsonError(
  status: number,
  error: string,
  message: string,
  headers: Record<string, string> = {},
): Response {
  return Response.json({ error, message }, { status, headers });
}
