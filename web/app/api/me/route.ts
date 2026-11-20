import { getAuth } from "@/lib/auth/server";

export const dynamic = "force-dynamic";

/** The signed-in user, or 401. Only id, email and name leave the server. */
export async function GET() {
  const { data: session } = await getAuth().getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });
  const { id, email, name } = session.user;
  return Response.json({ id, email, name });
}
