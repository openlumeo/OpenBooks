import { redirect } from "next/navigation";
import { getAuth } from "@/lib/auth/server";
import { safeNextPath } from "@/lib/auth/next-path";

export async function redirectIfSignedIn(rawNext: string | string[] | undefined): Promise<string> {
  const next = safeNextPath(rawNext);
  let signedIn = false;
  try {
    const { data: session } = await getAuth().getSession();
    signedIn = Boolean(session?.user);
  } catch {}
  if (signedIn) redirect(next);
  return next;
}
