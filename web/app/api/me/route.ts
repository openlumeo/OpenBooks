import { getAuth } from "@/lib/auth/server";
import { NO_STORE_HEADERS } from "@/lib/http";

export const dynamic = "force-dynamic";

/** The signed-in user, or 401. Only id, email and name leave the server. */
export async function GET() {
  const { data: session } = await getAuth().getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401, headers: NO_STORE_HEADERS });
  const { id, email, name } = session.user;
  return Response.json({ id, email, name }, { headers: NO_STORE_HEADERS });
}
