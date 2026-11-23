import { readFileSync } from "node:fs";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { findEngine, runFile } from "@lumeo_hq/openbooks-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { INSTRUCTIONS, MAX_STEPS, PROMPT_NAMES, REFUSAL_CODES, RESOURCE_URIS, SAMPLE_STATEMENT, TOOL_NAMES } from "../src/constants.js";
import { buildServer, packageVersion } from "../src/server.js";
import { ENGINE, released } from "./helpers.js";

vi.mock("@lumeo_hq/openbooks-core", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@lumeo_hq/openbooks-core")>()),
  runFile: vi.fn(),
  findEngine: vi.fn(),
}));

let client: Client;

async function connect(): Promise<Client> {
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair();
  await buildServer().connect(serverSide);
  const created = new Client({ name: "test", version: "1.0.0" });
  await created.connect(clientSide);
  return created;
}

beforeEach(async () => {
  vi.mocked(runFile).mockReset().mockImplementation(async () => released("statement.csv"));
  vi.mocked(findEngine).mockReset().mockResolvedValue(ENGINE);
  client = await connect();
});

afterEach(async () => {
  await client.close();
});

const text = (result: object): string => {
  const first = ((result as { content?: unknown }).content as { type: string; text: string }[])[0];
  return first?.text ?? "";
};

const promptText = (messages: { content: unknown }[]): string => String((messages[0]?.content as { text: string }).text);

describe("server identity", () => {
  it("reports name, title and package version", () => {
    expect(client.getServerVersion()).toMatchObject({ name: "openbooks", title: "Open Books", version: packageVersion() });
  });

  it("matches package.json", () => {
    const manifest = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };
    expect(packageVersion()).toBe(manifest.version);
  });

  it("sends the instructions", () => {
    expect(client.getInstructions()).toBe(INSTRUCTIONS);
  });

  it.each(["parallel", "stop_on_error", "$ref", "verify_many", "capabilities", "packages"])("instructions mention %s", (word) => {
    expect(INSTRUCTIONS).toContain(word);
  });

  it("advertises tools, resources and prompts", () => {
    expect(Object.keys(client.getServerCapabilities() ?? {})).toEqual(expect.arrayContaining(["tools", "resources", "prompts"]));
  });
});

describe("tools", () => {
  it("exposes exactly the two documented tools", async () => {
    const { tools } = await client.listTools();
    expect(tools.map((tool) => tool.name).sort()).toEqual([...TOOL_NAMES].sort());
  });

  it.each(TOOL_NAMES)("%s declares an output schema", async (name) => {
    const tool = (await client.listTools()).tools.find((entry) => entry.name === name);
    expect(tool?.outputSchema).toMatchObject({ type: "object" });
  });

  it.each(TOOL_NAMES)("%s is annotated read-only and closed-world", async (name) => {
    const tool = (await client.listTools()).tools.find((entry) => entry.name === name);
    expect(tool?.annotations).toMatchObject({ readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false });
  });

  it.each(TOOL_NAMES)("%s has a title and a description", async (name) => {
    const tool = (await client.listTools()).tools.find((entry) => entry.name === name);
    expect(tool?.title?.length).toBeGreaterThan(3);
    expect(tool?.description?.length).toBeGreaterThan(20);
  });

  it("execute input has steps, parallel and stop_on_error", async () => {
    const tool = (await client.listTools()).tools.find((entry) => entry.name === "execute");
    expect(Object.keys(tool?.inputSchema.properties ?? {}).sort()).toEqual(["parallel", "steps", "stop_on_error"]);
    expect(tool?.inputSchema.required).toEqual(["steps"]);
  });

  it("execute limits steps to MAX_STEPS", async () => {
    const tool = (await client.listTools()).tools.find((entry) => entry.name === "execute");
    const steps = (tool?.inputSchema.properties?.steps ?? {}) as { minItems?: number; maxItems?: number };
    expect(steps).toMatchObject({ minItems: 1, maxItems: MAX_STEPS });
  });

  it("search returns structured and text content", async () => {
    const result = await client.callTool({ name: "search", arguments: { query: "verify" } });
    expect(result.structuredContent).toMatchObject({ max_steps: MAX_STEPS });
    expect(JSON.parse(text(result))).toEqual(result.structuredContent);
  });

  it("search lists every operation for an empty query", async () => {
    const result = await client.callTool({ name: "search", arguments: {} });
    expect((result.structuredContent as { operations: unknown[] }).operations).toHaveLength(9);
  });

  it("execute runs a batch with a doctor step", async () => {
    const result = await client.callTool({ name: "execute", arguments: { steps: [{ id: "d", operation: "doctor" }] } });
    const steps = (result.structuredContent as { steps: { result: { healthy: boolean } }[] }).steps;
    expect(steps[0]?.result.healthy).toBe(true);
  });

  it("execute supports $ref and parallel flags end to end", async () => {
    const result = await client.callTool({
      name: "execute",
      arguments: {
        steps: [
          { id: "a", operation: "process_sample", arguments: {} },
          { id: "b", operation: "process_sample", arguments: { opening: { $ref: "a.data.opening" } } },
        ],
      },
    });
    const steps = (result.structuredContent as { steps: { result?: { status: string } }[] }).steps;
    expect(steps.map((step) => step.result?.status)).toEqual(["ok", "ok"]);
    const parallel = await client.callTool({ name: "execute", arguments: { parallel: true, steps: [{ id: "a", operation: "doctor" }, { id: "b", operation: "formats" }] } });
    expect((parallel.structuredContent as { steps: unknown[] }).steps).toHaveLength(2);
  });

  it("execute output is compact JSON", async () => {
    const result = await client.callTool({ name: "execute", arguments: { steps: [{ id: "c", operation: "capabilities" }] } });
    expect(text(result)).not.toContain("\n");
  });

  it("execute returns a step-level error for unknown operations", async () => {
    const result = await client.callTool({ name: "execute", arguments: { steps: [{ id: "x", operation: "nope" }] } });
    expect(result.isError).toBeFalsy();
    expect(JSON.stringify(result.structuredContent)).toContain("UNKNOWN_OPERATION");
  });

  it.each([
    ["no steps", { steps: [] }],
    ["too many steps", { steps: Array.from({ length: 9 }, (_v, i) => ({ id: `s${i}`, operation: "doctor" })) }],
    ["bad step id", { steps: [{ id: "1", operation: "doctor" }] }],
    ["missing steps", {}],
    ["parallel not boolean", { steps: [{ id: "a", operation: "doctor" }], parallel: "yes" }],
  ])("execute rejects %s", async (_label, args) => {
    const result = await client.callTool({ name: "execute", arguments: args }).catch(() => ({ isError: true }));
    expect(result.isError).toBe(true);
  });

  it("reports DUPLICATE_STEP as a top-level error", async () => {
    const result = await client.callTool({ name: "execute", arguments: { steps: [{ id: "a", operation: "doctor" }, { id: "a", operation: "doctor" }] } });
    expect(result.structuredContent).toMatchObject({ error: { code: "DUPLICATE_STEP" } });
  });
});

describe("resources", () => {
  it("lists exactly the documented resources", async () => {
    const { resources } = await client.listResources();
    expect(resources.map((resource) => resource.uri).sort()).toEqual([...RESOURCE_URIS].sort());
  });

  it.each(RESOURCE_URIS)("%s has a mime type and description", async (uri) => {
    const resource = (await client.listResources()).resources.find((entry) => entry.uri === uri);
    expect(resource?.mimeType).toBeTruthy();
    expect(resource?.description).toBeTruthy();
  });

  it.each(RESOURCE_URIS)("%s is readable", async (uri) => {
    const { contents } = await client.readResource({ uri });
    expect(contents).toHaveLength(1);
    expect(String((contents[0] as { text?: string } | undefined)?.text).length).toBeGreaterThan(10);
  });

  it("serves the sample statement verbatim", async () => {
    const { contents } = await client.readResource({ uri: "openbooks://samples/statement.csv" });
    expect((contents[0] as { text?: string } | undefined)?.text).toBe(SAMPLE_STATEMENT);
  });

  it.each(Object.keys(REFUSAL_CODES))("the refusal guide documents %s", async (code) => {
    const { contents } = await client.readResource({ uri: "openbooks://guide/refusals" });
    expect(String((contents[0] as { text?: string } | undefined)?.text)).toContain(`\`${code}\``);
  });

  it("serves the released schema as JSON", async () => {
    const { contents } = await client.readResource({ uri: "openbooks://schema/released" });
    const schema = JSON.parse(String((contents[0] as { text?: string } | undefined)?.text)) as { properties?: Record<string, unknown> };
    expect(schema.properties).toHaveProperty("schema_version");
  });

  it("rejects an unknown resource", async () => {
    await expect(client.readResource({ uri: "openbooks://nope" })).rejects.toThrow();
  });
});

describe("prompts", () => {
  it("lists exactly the documented prompts", async () => {
    const { prompts } = await client.listPrompts();
    expect(prompts.map((prompt) => prompt.name).sort()).toEqual([...PROMPT_NAMES].sort());
  });

  it.each(PROMPT_NAMES)("%s has a description", async (name) => {
    const prompt = (await client.listPrompts()).prompts.find((entry) => entry.name === name);
    expect(prompt?.description).toBeTruthy();
  });

  it("verify_document names the path and opening", async () => {
    const { messages } = await client.getPrompt({ name: "verify_document", arguments: { path: "jan.csv", opening: "10.00" } });
    const body = promptText(messages);
    expect(body).toContain("jan.csv");
    expect(body).toContain("10.00");
    expect(body).toContain("process_file");
  });

  it("verify_document omits opening when absent", async () => {
    const { messages } = await client.getPrompt({ name: "verify_document", arguments: { path: "jan.csv" } });
    expect(promptText(messages)).not.toContain("opening \"");
  });

  it.each(Object.keys(REFUSAL_CODES))("explain_refusal explains %s", async (code) => {
    const { messages } = await client.getPrompt({ name: "explain_refusal", arguments: { code } });
    expect(promptText(messages)).toContain(REFUSAL_CODES[code]);
  });

  it.each(["NOT_A_CODE", "constructor", "__proto__", "toString"])("explain_refusal treats %s as unknown", async (code) => {
    const { messages } = await client.getPrompt({ name: "explain_refusal", arguments: { code } });
    expect(promptText(messages)).toContain("not a known refusal code");
  });

  it("try_sample drives doctor, process_sample and records", async () => {
    const { messages } = await client.getPrompt({ name: "try_sample" });
    const body = promptText(messages);
    expect(body).toContain("doctor");
    expect(body).toContain("process_sample");
    expect(body).toContain("records");
  });
});
