import { NextResponse, type NextRequest } from "next/server";
import { getAuth } from "@/lib/auth/server";
import { signInUrlFor } from "@/lib/auth/next-path";

const SIGN_IN_PATH = "/auth/sign-in";
const SESSION_VERIFIER = "neon_auth_session_verifier";

export async function proxy(request: NextRequest) {
  const target = request.nextUrl.clone();
  if (target.searchParams.has(SESSION_VERIFIER)) {
    target.searchParams.delete(SESSION_VERIFIER);
  }
  const signIn = new URL(signInUrlFor(target.pathname, target.search), request.url);

  try {
    const response = await getAuth().middleware({ loginUrl: SIGN_IN_PATH })(request);
    const location = response.headers.get("location");
    if (location) {
      const destination = new URL(location, request.url);
      if (destination.origin === signIn.origin && destination.pathname === SIGN_IN_PATH) {
        response.headers.set("location", signIn.href);
      }
    }
    return response;
  } catch {}
  return NextResponse.redirect(signIn);
}

export const config = {
  matcher: [
    "/app/:path*",
    { source: "/:path*", has: [{ type: "query", key: "neon_auth_session_verifier" }] },
  ],
};
