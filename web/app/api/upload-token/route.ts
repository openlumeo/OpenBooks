import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { getAuth } from "@/lib/auth/server";
import { jsonError, NO_STORE_HEADERS } from "@/lib/http";
import { limitOr429 } from "@/lib/server/limiter";

const SITE = "https://books.openlumeo.com";
const JOB = /^[a-f0-9]{32}$/;
const TTL_SECONDS = 1800;

function signature(secret: string, job: string, expires: string, owner = ""): Buffer {
  const payload = owner ? `${job}.${expires}.${owner}` : `${job}.${expires}`;
  return createHmac("sha256", secret).update(`openbooks-upload-v1:${payload}`).digest();
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
  const retain = req.headers.get("x-openbooks-retain") === "1";
  if (retain && process.env.OPENBOOKS_RETENTION_ENABLED !== "1") {
    return jsonError(503, "retention_unavailable", "Saving originals is temporarily unavailable.", NO_STORE_HEADERS);
  }
  const owner = retain ? createHash("sha256").update(session.user.id).digest("hex") : "";
  const expires = String(Math.floor(Date.now() / 1000) + TTL_SECONDS);
  const mac = signature(secret, job, expires, owner).toString("hex");
  return Response.json({ token: owner ? `${expires}.${mac}.${owner}` : `${expires}.${mac}` }, { headers: NO_STORE_HEADERS });
}

export function GET(req: Request) {
  const secret = process.env.OPENBOOKS_UPLOAD_SECRET ?? process.env.OPENBOOKS_ENGINE_KEY;
  const job = req.headers.get("x-openbooks-job") ?? "";
  const [, expires, mac, owner] = /^Bearer (\d{10})\.([a-f0-9]{64})(?:\.([a-f0-9]{64}))?$/.exec(req.headers.get("authorization") ?? "") ?? [];
  const now = Math.floor(Date.now() / 1000);
  const valid = secret && JOB.test(job) && expires && mac && Number(expires) >= now && Number(expires) <= now + TTL_SECONDS
    && (!owner || process.env.OPENBOOKS_RETENTION_ENABLED === "1")
    && timingSafeEqual(Buffer.from(mac, "hex"), signature(secret, job, expires, owner));
  const headers = valid && owner ? { ...NO_STORE_HEADERS, "x-openbooks-retain-owner": owner } : NO_STORE_HEADERS;
  return new Response(null, { status: valid ? 204 : 401, headers });
}
