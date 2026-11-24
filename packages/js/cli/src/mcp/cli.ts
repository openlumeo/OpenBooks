#!/usr/bin/env node
import { realpathSync, statSync } from "node:fs";
import { parseArgs } from "node:util";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import type { DiscoverOptions } from "@lumeo_hq/openbooks-core";
import { DEFAULT_HTTP_PORT, MIN_TOKEN_LENGTH, SERVER_NAME } from "./constants.js";
import { startHttp } from "./http.js";
import { buildServer, packageVersion } from "./server.js";

const TOKEN_ENV = "OPENBOOKS_MCP_TOKEN";
const MAX_PORT = 65535;
const USAGE = `Usage: openbooks-mcp [--root <dir>] [--python <path>]
       openbooks-mcp --http [--port <n>] [--python <path>]   (token from ${TOKEN_ENV})

Options:
  --root <dir>     Approved folder for process_file (stdio only)
  --http           Serve Streamable HTTP on 127.0.0.1 instead of stdio
  --port <n>       HTTP port (default ${DEFAULT_HTTP_PORT})
  --python <path>  Python interpreter for the Open Books engine
  -h, --help       Show this help
  -v, --version    Show the version`;

class UsageError extends Error {}

interface CliArguments {
  root: string | undefined;
  http: boolean;
  port: number;
  python: string | undefined;
  help: boolean;
  version: boolean;
}

function fail(message: string): never {
  throw new UsageError(message);
}

function parsePort(raw: string | undefined): number {
  if (raw === undefined) return DEFAULT_HTTP_PORT;
  if (!/^[0-9]+$/.test(raw)) fail("--port must be an integer.");
  const port = Number(raw);
  if (port < 1 || port > MAX_PORT) fail(`--port must be between 1 and ${MAX_PORT}.`);
  return port;
}

function parseCli(argv: readonly string[]): CliArguments {
  let parsed: ReturnType<typeof parseArgs<{ options: typeof OPTIONS }>>;
  try {
    parsed = parseArgs({ args: [...argv], options: OPTIONS, strict: true, allowPositionals: false });
  } catch (error: unknown) {
    fail(error instanceof Error ? error.message : "Invalid arguments.");
  }
  const { values } = parsed;
  return {
    root: values.root,
    http: values.http ?? false,
    port: parsePort(values.port),
    python: values.python,
    help: values.help ?? false,
    version: values.version ?? false,
  };
}

const OPTIONS = {
  root: { type: "string" },
  http: { type: "boolean" },
  port: { type: "string" },
  python: { type: "string" },
  help: { type: "boolean", short: "h" },
  version: { type: "boolean", short: "v" },
} as const;

function resolveRoot(raw: string): string {
  let resolved: string;
  try {
    resolved = realpathSync(raw);
  } catch {
    fail(`--root path does not exist: ${raw}`);
  }
  if (!statSync(resolved).isDirectory()) fail(`--root must be a directory: ${raw}`);
  return resolved;
}

function engineOptions(python: string | undefined): DiscoverOptions {
  return python === undefined ? {} : { python };
}

async function runStdio(args: CliArguments): Promise<void> {
  const root = args.root === undefined ? undefined : resolveRoot(args.root);
  const server = buildServer({ root, engine: engineOptions(args.python) });
  await server.connect(new StdioServerTransport());
  process.stderr.write(`${SERVER_NAME} MCP server running on stdio\n`);
}

async function runHttp(args: CliArguments): Promise<void> {
  if (args.root !== undefined) fail("--root is not allowed with --http.");
  const token = process.env[TOKEN_ENV];
  if (token === undefined || token === "") fail(`${TOKEN_ENV} must be set for --http (at least ${MIN_TOKEN_LENGTH} characters).`);
  const running = await startHttp({ port: args.port, token, engine: engineOptions(args.python) });
  process.stderr.write(`${SERVER_NAME} MCP server listening on http://127.0.0.1:${running.port}/mcp\n`);
}

async function main(argv: readonly string[]): Promise<number> {
  const args = parseCli(argv);
  if (args.help) {
    process.stdout.write(`${USAGE}\n`);
    return 0;
  }
  if (args.version) {
    process.stdout.write(`${packageVersion()}\n`);
    return 0;
  }
  if (args.http) {
    await runHttp(args);
  } else {
    await runStdio(args);
  }
  return 0;
}

main(process.argv.slice(2)).then(
  (code) => {
    if (code !== 0) process.exitCode = code;
  },
  (error: unknown) => {
    const message = error instanceof Error ? error.message : "Unexpected error.";
    process.stderr.write(`openbooks-mcp: ${message}\n`);
    process.exitCode = error instanceof UsageError ? 2 : 1;
  },
);
