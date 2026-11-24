import { timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { DiscoverOptions } from "../core/index.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { MAX_HTTP_BODY_BYTES, MIN_TOKEN_LENGTH } from "./constants.js";
import { Operations } from "./operations.js";
import { buildServer } from "./server.js";

export interface HttpOptions {
  port: number;
  token: string;
  engine?: DiscoverOptions;
}

export interface RunningHttpServer {
  port: number;
  close(): Promise<void>;
}

const MCP_PATH = "/mcp";
const HOST = "127.0.0.1";
const TOKEN_PATTERN = /^[\x21-\x7e]+$/;
const BEARER_PATTERN = /^Bearer (.+)$/;
const LOCAL_HOSTS: ReadonlySet<string> = new Set(["localhost", "127.0.0.1"]);

class HttpFailure extends Error {
  constructor(readonly status: number, message: string, readonly headers: Record<string, string> = {}) {
    super(message);
  }
}

function assertToken(token: string): void {
  if (!TOKEN_PATTERN.test(token) || token.length < MIN_TOKEN_LENGTH) {
    throw new Error(`The MCP token must be ASCII with at least ${MIN_TOKEN_LENGTH} characters.`);
  }
}

function sendJson(res: ServerResponse, status: number, body: Record<string, unknown>, headers: Record<string, string> = {}): void {
  res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers });
  res.end(JSON.stringify(body));
}

function sendFailure(res: ServerResponse, failure: HttpFailure): void {
  sendJson(res, failure.status, { error: failure.message }, failure.headers);
}

function checkOrigin(req: IncomingMessage): void {
  const origin = req.headers.origin;
  if (origin === undefined) return;
  let host: string;
  try {
    host = new URL(origin).hostname;
  } catch {
    throw new HttpFailure(403, "Origin is not allowed.");
  }
  if (!LOCAL_HOSTS.has(host)) throw new HttpFailure(403, "Origin is not allowed.");
}

function tokenMatches(presented: string, expected: string): boolean {
  const left = Buffer.from(presented, "utf8");
  const right = Buffer.from(expected, "utf8");
  if (left.length !== right.length) return false;
  return timingSafeEqual(left, right);
}

function checkAuthorization(req: IncomingMessage, token: string): void {
  const header = req.headers.authorization ?? "";
  const match = BEARER_PATTERN.exec(header);
  const presented = match?.[1] ?? "";
  if (presented === "" || !tokenMatches(presented, token)) {
    throw new HttpFailure(401, "A valid bearer token is required.", { "WWW-Authenticate": "Bearer" });
  }
}

function checkRoute(req: IncomingMessage): void {
  const path = new URL(req.url ?? "/", `http://${HOST}`).pathname;
  if (path !== MCP_PATH) throw new HttpFailure(404, "Not found.");
  if (req.method !== "POST") throw new HttpFailure(405, "Method not allowed.", { Allow: "POST" });
}

function readBody(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let total = 0;
    req.on("data", (chunk: Buffer) => {
      total += chunk.length;
      if (total > MAX_HTTP_BODY_BYTES) {
        reject(new HttpFailure(413, "Request body is too large."));
        req.resume();
        return;
      }
      chunks.push(chunk);
    });
    req.on("error", () => reject(new HttpFailure(400, "Request body could not be read.")));
    req.on("end", () => {
      if (total > MAX_HTTP_BODY_BYTES) return;
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      } catch {
        reject(new HttpFailure(400, "Request body must be JSON."));
      }
    });
  });
}

async function handleMcp(req: IncomingMessage, res: ServerResponse, options: HttpOptions, operations: Operations): Promise<void> {
  checkRoute(req);
  checkOrigin(req);
  checkAuthorization(req, options.token);
  const body = await readBody(req);
  const server = buildServer({ operations });
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  res.on("close", () => {
    void transport.close();
    void server.close();
  });
  await server.connect(transport);
  await transport.handleRequest(req, res, body);
}

function handleRequest(req: IncomingMessage, res: ServerResponse, options: HttpOptions, operations: Operations): void {
  handleMcp(req, res, options, operations).catch((error: unknown) => {
    if (error instanceof HttpFailure) {
      if (!res.headersSent) sendFailure(res, error);
      else res.end();
      return;
    }
    process.stderr.write(`openbooks-mcp: request failed: ${error instanceof Error ? error.message : "unknown error"}\n`);
    if (!res.headersSent) sendJson(res, 500, { error: "Internal error." });
    else res.end();
  });
}

function listen(server: Server, port: number): Promise<number> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, HOST, () => {
      const address = server.address();
      if (address === null || typeof address === "string") {
        reject(new Error("The HTTP server did not report a TCP port."));
        return;
      }
      resolve(address.port);
    });
  });
}

export async function startHttp(options: HttpOptions): Promise<RunningHttpServer> {
  assertToken(options.token);
  const operations = new Operations({ engine: options.engine });
  const server = createServer((req, res) => handleRequest(req, res, options, operations));
  const port = await listen(server, options.port);
  return {
    port,
    close: () => new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve()))),
  };
}
