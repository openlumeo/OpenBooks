import { MAX_UPLOAD_BYTES, rejectNonMultipart, rejectOversize } from "@/lib/guards";
import { NO_STORE_HEADERS } from "@/lib/http";
import { proxyJobStatus, proxyUpload } from "@/lib/server/engine";
import { limitOr429 } from "@/lib/server/limiter";

export const dynamic = "force-dynamic";

export function GET(req: Request) {
  return proxyJobStatus(req, "/v1/roles");
}

export async function POST(req: Request) {
  const limited = await limitOr429(req, "roles");
  if (limited) return limited;
  const notMultipart = rejectNonMultipart(req.headers.get("content-type") ?? "");
  if (notMultipart) return notMultipart;
  const tooBig = rejectOversize(req, MAX_UPLOAD_BYTES);
  if (tooBig) return tooBig;
  return proxyUpload(req, "/v1/roles", NO_STORE_HEADERS);
}
