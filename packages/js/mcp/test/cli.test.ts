import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { findEngine } from "@lumeo_hq/openbooks-core";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const CLI = join(import.meta.dirname, "..", "dist", "cli.js");
const MCP_PACKAGE = join(import.meta.dirname, "..", "package.json");
const VERSION = (JSON.parse(readFileSync(MCP_PACKAGE, "utf8")) as { version: string }).version;
const engineAvailable = await findEngine().then(() => true, () => false);

function cli(args: string[], env: Record<string, string> = {}): { code: number | null; stdout: string; stderr: string } {
  const merged: NodeJS.ProcessEnv = { ...process.env, ...env };
  if (env.OPENBOOKS_MCP_TOKEN === undefined) delete merged.OPENBOOKS_MCP_TOKEN;
  const run = spawnSync(process.execPath, [CLI, ...args], { encoding: "utf8", env: merged, timeout: 20_000 });
  return { code: run.status, stdout: run.stdout, stderr: run.stderr };
}

describe("argument parsing", () => {
  it.each([
    ["--help", ["--help"]],
    ["-h", ["-h"]],
    ["--help with --http", ["--help", "--http"]],
    ["--help with a bad port", ["--help", "--port", "123"]],
  ])("prints usage for %s", (_label, args) => {
    const run = cli(args);
    expect(run.code).toBe(0);
    expect(run.stdout).toContain("Usage: openbooks-mcp");
  });

  it.each(["--version", "-v"])("prints the version for %s", (flag) => {
    const run = cli([flag]);
    expect(run.code).toBe(0);
    expect(run.stdout.trim()).toBe(VERSION);
  });

  it.each([
    ["unknown flag", ["--bogus"]],
    ["positional argument", ["extra"]],
    ["missing root value", ["--root"]],
    ["non-numeric port", ["--port", "abc"]],
    ["port zero", ["--port", "0"]],
    ["port above range", ["--port", "65536"]],
    ["negative port", ["--port=-1"]],
    ["fractional port", ["--port", "1.5"]],
    ["empty port", ["--port", ""]],
    ["missing root directory", ["--root", join(tmpdir(), "openbooks-mcp-does-not-exist")]],
    ["root that is a file", ["--root", MCP_PACKAGE]],
    ["root combined with http", ["--http", "--root", tmpdir()]],
  ])("exits 2 for %s", (_label, args) => {
    const run = cli(args, { OPENBOOKS_MCP_TOKEN: "t".repeat(32) });
    expect(run.code).toBe(2);
    expect(run.stderr).toContain("openbooks-mcp:");
  });

  it("exits 2 when --http has no token", () => {
    const run = cli(["--http", "--port", "48791"]);
    expect(run.code).toBe(2);
    expect(run.stderr).toContain("OPENBOOKS_MCP_TOKEN");
  });

  it("exits 2 when the token is empty", () => {
    expect(cli(["--http", "--port", "48791"], { OPENBOOKS_MCP_TOKEN: "" }).code).toBe(2);
  });

  it("exits 1 when the token is too short", () => {
    const run = cli(["--http", "--port", "48792"], { OPENBOOKS_MCP_TOKEN: "short" });
    expect(run.code).toBe(1);
    expect(run.stderr).toContain("at least 32");
  });

  it("serves HTTP with a valid token and port", async () => {
    const port = 48793;
    const child = spawn(process.execPath, [CLI, "--http", "--port", String(port)], { env: { ...process.env, OPENBOOKS_MCP_TOKEN: "t".repeat(32) } });
    try {
      await new Promise<void>((resolve, reject) => {
        child.stderr.on("data", (chunk: Buffer) => {
          if (chunk.toString().includes("listening")) resolve();
        });
        child.on("error", reject);
        child.on("exit", () => reject(new Error("exited early")));
      });
      const unauthorised = await fetch(`http://127.0.0.1:${port}/mcp`, { method: "POST", body: "{}" });
      expect(unauthorised.status).toBe(401);
    } finally {
      child.kill();
    }
  });
});

describe("stdio end to end", () => {
  let folder: string;

  beforeAll(() => {
    folder = realpathSync(mkdtempSync(join(tmpdir(), "ob-mcp-e2e-")));
    writeFileSync(join(folder, "statement.csv"), "Date,Description,Debit,Credit,Balance\n02/01/2026,Sample payment,100.00,,900.00\n03/01/2026,Sample deposit,,50.00,950.00\n");
  });

  afterAll(() => {
    rmSync(folder, { recursive: true, force: true });
  });

  async function connect(args: string[]): Promise<Client> {
    const client = new Client({ name: "e2e", version: "1.0.0" });
    await client.connect(new StdioClientTransport({ command: process.execPath, args: [CLI, ...args], stderr: "ignore" }));
    return client;
  }

  it("lists tools and answers search without an engine", async () => {
    const client = await connect([]);
    try {
      expect((await client.listTools()).tools.map((tool) => tool.name).sort()).toEqual(["execute", "search"]);
      const found = await client.callTool({ name: "search", arguments: { query: "capabilities" } });
      expect(JSON.stringify(found.structuredContent)).toContain("capabilities");
    } finally {
      await client.close();
    }
  });

  it("exposes process_file only when --root is set", async () => {
    const client = await connect(["--root", folder]);
    try {
      const found = await client.callTool({ name: "search", arguments: { query: "process_file" } });
      expect(JSON.stringify(found.structuredContent)).toContain("process_file");
    } finally {
      await client.close();
    }
  });

  it.skipIf(!engineAvailable)("verifies a local file with the real engine", async () => {
    const client = await connect(["--root", folder]);
    try {
      const options = { currency: "INR", date_order: "dmy", opening: "1000.00" };
      const result = await client.callTool({
        name: "execute",
        arguments: {
          steps: [
            { id: "d", operation: "doctor" },
            { id: "f", operation: "process_file", arguments: { path: "statement.csv", ...options } },
            { id: "m", operation: "verify_many", arguments: { files: ["statement.csv", "../x.csv"], ...options } },
          ],
          stop_on_error: false,
        },
      });
      const steps = (result.structuredContent as { steps: { result: Record<string, unknown> }[] }).steps;
      expect(steps[0]?.result.healthy).toBe(true);
      expect(steps[1]?.result.status).toBe("ok");
      expect(steps[2]?.result).toMatchObject({ total: 2, ok: 1, error: 1 });
    } finally {
      await client.close();
    }
  }, 120_000);
});
