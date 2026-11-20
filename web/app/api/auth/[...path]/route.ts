import { getAuth } from "@/lib/auth/server";

type Handlers = ReturnType<ReturnType<typeof getAuth>["handler"]>;
type Ctx = Parameters<Handlers["GET"]>[1];

const call = (method: keyof Handlers) => (req: Request, ctx: Ctx) =>
  (getAuth().handler()[method] as (r: Request, c: Ctx) => Promise<Response>)(req, ctx);

export const GET = call("GET");
export const POST = call("POST");
export const PUT = call("PUT");
export const DELETE = call("DELETE");
export const PATCH = call("PATCH");
