import { createHmac, timingSafeEqual } from "node:crypto";
import { getAuth } from "@/lib/auth/server";
import { jsonError, NO_STORE_HEADERS } from "@/lib/http";
import { limitOr429 } from "@/lib/server/limiter";

const SITE = "https://books.openlumeo.com";
const JOB = /^[a-f0-9]{32}$/;
const TTL_SECONDS = 1800;

function signature(secret: string, job: string, expires: string): Buffer {
  return createHmac("sha256", secret).update(`openbooks-upload-v1:${job}.${expires}`).digest();
}

export async function POST(req: Request) {
  const secret = process.env.OPENBOOKS_UPLOAD_SECRET ?? process.env.OPENBOOKS_ENGINE_KEY;
  if (!secret) return jsonError(503, "upload_unavailable", "Large uploads are unavailable.", NO_STORE_HEADERS);
  if (req.headers.get("origin") !== SITE) return new Response(null, { status: 403, headers: NO_STORE_HEADERS });
  const job = req.headers.get("x-openbooks-job") ?? "";
  if (!JOB.test(job)) return new Response(null, { status: 400, headers: NO_STORE_HEADERS });
  const limited = await limitOr429(req, "runs");
  if (limited) return limited;
  const { data: session } = await getAuth().getSession();
  if (!session?.user) return jsonError(401, "sign_in_required", "Sign in to upload a large file.", NO_STORE_HEADERS);
  const expires = String(Math.floor(Date.now() / 1000) + TTL_SECONDS);
  return Response.json({ token: `${expires}.${signature(secret, job, expires).toString("hex")}` }, { headers: NO_STORE_HEADERS });
}

export function GET(req: Request) {
  const secret = process.env.OPENBOOKS_UPLOAD_SECRET ?? process.env.OPENBOOKS_ENGINE_KEY;
  const job = req.headers.get("x-openbooks-job") ?? "";
  const [, expires, mac] = /^Bearer (\d{10})\.([a-f0-9]{64})$/.exec(req.headers.get("authorization") ?? "") ?? [];
  const now = Math.floor(Date.now() / 1000);
  const valid = secret && JOB.test(job) && expires && mac && Number(expires) >= now && Number(expires) <= now + TTL_SECONDS
    && timingSafeEqual(Buffer.from(mac, "hex"), signature(secret, job, expires));
  return new Response(null, { status: valid ? 204 : 401, headers: NO_STORE_HEADERS });
}
