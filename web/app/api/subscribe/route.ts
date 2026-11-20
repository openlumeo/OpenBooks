import { neon } from "@neondatabase/serverless";
import { parseSubscribe } from "@/lib/subscribe";
import { limitOr429 } from "@/lib/server/limiter";

export const dynamic = "force-dynamic";

const MAX_BODY_BYTES = 2048;

function jsonResponse(
  body: Record<string, unknown>,
  status: number,
  extraHeaders: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...extraHeaders,
    },
  });
}

function isJsonContentType(contentType: string | null): boolean {
  return contentType?.split(";")[0]?.trim().toLowerCase() === "application/json";
}

function parseJson(text: string): { ok: true; value: unknown } | { ok: false } {
  try {
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false };
  }
}

function describeError(error: unknown): { name: string; message: string } {
  if (error instanceof Error) return { name: error.name, message: error.message };
  return { name: "UnknownError", message: "non-Error value thrown" };
}

async function saveSubscriber(email: string): Promise<void> {
  const sql = neon(process.env.DATABASE_URL ?? "");
  await sql`INSERT INTO public.subscribers (email) VALUES (${email}) ON CONFLICT DO NOTHING`;
}

export async function POST(request: Request): Promise<Response> {
  const limited = await limitOr429(request, "subscribe");
  if (limited) return limited;

  if (!isJsonContentType(request.headers.get("content-type"))) {
    return jsonResponse(
      { error: "unsupported_media_type", message: "Send application/json." },
      415,
    );
  }

  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > MAX_BODY_BYTES) {
    return jsonResponse({ error: "payload_too_large", message: "Request body is too large." }, 413);
  }

  const parsed = parseJson(text);
  if (!parsed.ok) {
    return jsonResponse({ error: "invalid_json", message: "Request body is not valid JSON." }, 400);
  }

  const result = parseSubscribe(parsed.value);
  if (!result.ok && result.reason === "spam") {
    return jsonResponse({ ok: true }, 200);
  }
  if (!result.ok) {
    return jsonResponse(
      { error: "invalid_email", message: "Enter a valid email address." },
      422,
    );
  }

  try {
    await saveSubscriber(result.email);
  } catch (error: unknown) {
    const { name, message } = describeError(error);
    console.error("subscribe_db_error", name, message);
    return jsonResponse(
      {
        error: "unavailable",
        message: "We couldn't save that right now. Please try again in a minute.",
      },
      503,
    );
  }

  return jsonResponse({ ok: true }, 200);
}
