import { NextResponse, type NextRequest } from "next/server";
import { getAuth } from "@/lib/auth/server";
import { signInUrlFor } from "@/lib/auth/next-path";

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  try {
    const { data: session } = await getAuth().getSession();
    if (session?.user) return NextResponse.next();
  } catch {}
  return NextResponse.redirect(new URL(signInUrlFor(pathname, search), request.url));
}

export const config = {
  matcher: ["/app", "/app/:path*"],
};
