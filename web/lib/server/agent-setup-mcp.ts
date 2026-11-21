import { McpServer, WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/server";
import { z } from "zod";
import { SETUP_TOKEN } from "@/lib/agent-setup";
import { readSmallJson } from "@/lib/guards";
import type { AgentSetupStore } from "./agent-setup-store";

const MCP_JSON_LIMIT = 8 * 1024;

export async function handleAgentSetupMcp(req: Request, store: Pick<AgentSetupStore, "confirm">) {
  let parsedBody: unknown;
  try {
    parsedBody = await readSmallJson(req, MCP_JSON_LIMIT);
  } catch (error) {
    const large = error instanceof Error && error.message === "body_limit";
    return Response.json({
      jsonrpc: "2.0", id: null, error: { code: -32700, message: large ? "MCP body is too large." : "Invalid JSON." },
    }, { status: large ? 413 : 400 });
  }
  const server = new McpServer({ name: "openbooks-agent-setup", version: "1.0.0" }, {
    instructions: "Confirm an Open Books agent setup code with the confirm_connection tool. Setup codes expire and grant no access to financial files.",
  });
  server.registerTool("confirm_connection", {
    title: "Confirm Open Books connection",
    description: "Confirm the one-time code displayed on the Open Books docs. This writes only the connection receipt.",
    inputSchema: z.object({ code: z.string().regex(SETUP_TOKEN) }).strict(),
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }, async ({ code }) => {
    const connected = await store.confirm(code);
    return {
      content: [{
        type: "text",
        text: connected
          ? "Open Books setup connection verified. Return to the docs to see the confirmation."
          : "This setup code has expired or is invalid. Start a new connection from the docs.",
      }],
      isError: !connected,
    };
  });

  const transport = new WebStandardStreamableHTTPServerTransport({ enableJsonResponse: true });
  await server.connect(transport);
  try {
    return await transport.handleRequest(req, { parsedBody });
  } finally {
    await server.close();
  }
}
