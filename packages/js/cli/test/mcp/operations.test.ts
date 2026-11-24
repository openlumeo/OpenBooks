import { mkdirSync, mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { EngineError, findEngine, runFile } from "@lumeo_hq/openbooks-core";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { EXTENSIONS, MAX_CONCURRENT_RUNS, MAX_ENCODED_UPLOAD, MAX_STEPS, MAX_UPLOAD_BYTES, PROMPT_NAMES, REFUSAL_CODES, RESOURCE_URIS, TOOL_NAMES } from "../src/constants.js";
import { Operations, StepSchema, type Doc } from "../src/operations.js";
import { WORKSPACE_PACKAGES } from "../src/workspace.generated.js";
import { call, encode, ENGINE, errorCode, refused, released, resultOf, sleep } from "./helpers.js";

vi.mock("@lumeo_hq/openbooks-core", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@lumeo_hq/openbooks-core")>()),
  runFile: vi.fn(),
  findEngine: vi.fn(),
}));

const runFileMock = vi.mocked(runFile);
const findEngineMock = vi.mocked(findEngine);

let root: string;
let outside: string;

beforeAll(() => {
  const base = realpathSync(mkdtempSync(join(tmpdir(), "ob-mcp-ops-")));
  root = join(base, "root");
  outside = join(base, "outside");
  mkdirSync(join(root, "sub"), { recursive: true });
  mkdirSync(outside);
  writeFileSync(join(root, "a.csv"), "x");
  writeFileSync(join(root, "..hidden.csv"), "x");
  writeFileSync(join(root, "sub", "b.csv"), "x");
  writeFileSync(join(root, "notes.exe"), "x");
  writeFileSync(join(root, "noextension"), "x");
  writeFileSync(join(root, "UPPER.CSV"), "x");
  writeFileSync(join(outside, "secret.csv"), "x");
  symlinkSync(outside, join(root, "escape"), "junction");
  symlinkSync(join(root, "sub"), join(root, "inner"), "junction");
});

afterAll(() => {
  rmSync(join(root, ".."), { recursive: true, force: true });
});

beforeEach(() => {
  runFileMock.mockReset();
  findEngineMock.mockReset();
  runFileMock.mockImplementation(async (file) => released(basename(file)));
  findEngineMock.mockResolvedValue(ENGINE);
});

const upload = (filename = "s.csv", content = "a,b\n1,2\n", extra: Doc = {}): Doc => ({ filename, content_base64: encode(content), ...extra });

describe("process_file path containment", () => {
  const invalidPaths: [string, string][] = [
    ["absolute posix", "/etc/passwd"],
    ["absolute windows drive", "C:\\Windows\\win.ini"],
    ["absolute windows drive forward slash", "C:/Windows/win.ini"],
    ["unc path", "\\\\server\\share\\x.csv"],
    ["leading parent", "../a.csv"],
    ["leading parent backslash", "..\\a.csv"],
    ["embedded parent", "sub/../../a.csv"],
    ["trailing parent", "sub/.."],
    ["bare parent", ".."],
    ["nul byte", "a.csv\0.txt"],
    ["nul at start", "\0a.csv"],
    ["root itself", "."],
    ["directory", "sub"],
    ["missing file", "missing.csv"],
    ["symlinked directory escaping root", "escape/secret.csv"],
    ["extension not allowed", "notes.exe"],
    ["no extension", "noextension"],
  ];

  it.each(invalidPaths)("rejects %s", async (_label, path) => {
    const item = await call(new Operations({ root }), "process_file", { path });
    expect(["INVALID_PATH", "UNSUPPORTED_INPUT"]).toContain(errorCode(item));
    expect(runFileMock).not.toHaveBeenCalled();
  });

  it.each([
    ["top-level file", "a.csv"],
    ["nested file", "sub/b.csv"],
    ...(process.platform === "win32" ? [["nested file with backslash", "sub\\b.csv"]] : []),
    ["file starting with dots", "..hidden.csv"],
    ["uppercase extension", "UPPER.CSV"],
    ["symlink that stays inside root", "inner/b.csv"],
  ])("accepts %s", async (_label, path) => {
    const item = await call(new Operations({ root }), "process_file", { path });
    expect(errorCode(item)).toBeUndefined();
    expect(resultOf(item).status).toBe("ok");
    expect(runFileMock).toHaveBeenCalledOnce();
  });

  it("passes the resolved real path to the engine", async () => {
    await call(new Operations({ root }), "process_file", { path: "inner/b.csv" });
    expect(runFileMock.mock.calls[0]?.[0]).toBe(join(root, "sub", "b.csv"));
  });

  it("is absent when no root is configured", async () => {
    const operations = new Operations();
    expect(errorCode(await call(operations, "process_file", { path: "a.csv" }))).toBe("UNKNOWN_OPERATION");
    expect(operations.search("", false).operations.map((item) => item.name)).not.toContain("process_file");
  });

  it.each([
    ["empty path", ""],
    ["path above 512 characters", `${"a".repeat(513)}.csv`],
  ])("rejects schema violations: %s", async (_label, path) => {
    expect(errorCode(await call(new Operations({ root }), "process_file", { path }))).toBe("INVALID_ARGUMENTS");
  });
});

describe("process_upload validation", () => {
  it.each(EXTENSIONS)("accepts extension %s", async (extension) => {
    const item = await call(new Operations(), "process_upload", upload(`s${extension}`));
    expect(errorCode(item)).toBeUndefined();
  });

  it.each([".exe", ".sh", ".js", ".zip", ".docx", ".html", ".bat", ".py", ".json"])("rejects extension %s", async (extension) => {
    const item = await call(new Operations(), "process_upload", upload(`s${extension}`));
    expect(errorCode(item)).toBe("UNSUPPORTED_INPUT");
    expect(runFileMock).not.toHaveBeenCalled();
  });

  it("rejects a name with no extension", async () => {
    expect(errorCode(await call(new Operations(), "process_upload", upload("statement")))).toBe("UNSUPPORTED_INPUT");
  });

  it("accepts an uppercase extension", async () => {
    expect(errorCode(await call(new Operations(), "process_upload", upload("S.CSV")))).toBeUndefined();
  });

  it.each([
    ["parent segment", "../a.csv"],
    ["forward slash", "a/b.csv"],
    ["backslash", "a\\b.csv"],
    ["leading dot", ".hidden.csv"],
    ["empty", ""],
    ["nul", "a\0.csv"],
  ])("rejects filename with %s", async (_label, filename) => {
    expect(errorCode(await call(new Operations(), "process_upload", upload(filename)))).toBe("INVALID_ARGUMENTS");
  });

  it.each([
    ["non-base64 characters", "not base64!!"],
    ["length not a multiple of four", "abcde"],
    ["data url prefix", "data:text/csv;base64,AAAA"],
    ["padding in the middle", "AA=AAAAA"],
    ["whitespace", "AAAA AAAA"],
    ["url-safe alphabet", "AA-_AAAA"],
    ["three padding characters", "AAA==="],
  ])("rejects base64 with %s", async (_label, content_base64) => {
    const item = await call(new Operations(), "process_upload", { filename: "s.csv", content_base64 });
    expect(errorCode(item)).toBe("INVALID_ENCODING");
    expect(runFileMock).not.toHaveBeenCalled();
  });

  it("rejects content shorter than four characters", async () => {
    expect(errorCode(await call(new Operations(), "process_upload", { filename: "s.csv", content_base64: "abc" }))).toBe("INVALID_ARGUMENTS");
  });

  it("rejects an encoded payload above the encoded limit", async () => {
    const item = await call(new Operations(), "process_upload", { filename: "s.csv", content_base64: "A".repeat(MAX_ENCODED_UPLOAD + 4) });
    expect(errorCode(item)).toBe("INVALID_ARGUMENTS");
  });

  it("rejects a decoded payload one byte over 1 MiB", async () => {
    const item = await call(new Operations(), "process_upload", upload("big.csv", "", { content_base64: encode(Buffer.alloc(MAX_UPLOAD_BYTES + 1, 65)) }));
    expect(errorCode(item)).toBe("INPUT_LIMIT");
    expect(runFileMock).not.toHaveBeenCalled();
  });

  it("accepts a decoded payload of exactly 1 MiB", async () => {
    const item = await call(new Operations(), "process_upload", upload("max.csv", "", { content_base64: encode(Buffer.alloc(MAX_UPLOAD_BYTES, 65)) }));
    expect(errorCode(item)).toBeUndefined();
  });

  it("writes the decoded bytes to a temp file and removes it afterwards", async () => {
    let seenPath = "";
    let seenBody = "";
    runFileMock.mockImplementationOnce(async (file) => {
      seenPath = file;
      const { readFileSync } = await import("node:fs");
      seenBody = readFileSync(file, "utf8");
      return released("x.csv");
    });
    await call(new Operations(), "process_upload", upload("payload.csv", "hello,world\n"));
    const { existsSync } = await import("node:fs");
    expect(basename(seenPath)).toBe("payload.csv");
    expect(seenBody).toBe("hello,world\n");
    expect(existsSync(seenPath)).toBe(false);
  });
});

describe("processing option mapping", () => {
  it("passes every option to the engine", async () => {
    const operations = new Operations({ engine: { python: "py" } });
    await call(operations, "process_upload", upload("s.csv", "a", { currency: "USD", opening: "-5.25", date_order: "mdy", account: "acct", allow_derived_opening: true, ocr: false, model: true }));
    expect(runFileMock.mock.calls[0]?.[1]).toMatchObject({
      python: "py", currency: "USD", opening: "-5.25", dateOrder: "mdy", account: "acct", allowDerivedOpening: true, ocr: false, model: true,
    });
  });

  it("applies defaults when options are omitted", async () => {
    await call(new Operations(), "process_upload", upload());
    const options = runFileMock.mock.calls[0]?.[1];
    expect(options).toMatchObject({ allowDerivedOpening: false, ocr: true, model: false });
    expect(options).not.toHaveProperty("currency");
    expect(options).not.toHaveProperty("opening");
  });

  it("process_sample runs the sample with INR and day-first dates", async () => {
    await call(new Operations(), "process_sample", { opening: "1000.00" });
    expect(runFileMock.mock.calls[0]?.[1]).toMatchObject({ currency: "INR", dateOrder: "dmy", opening: "1000.00" });
  });

  it.each([
    ["currency lowercase", { currency: "usd" }],
    ["currency too long", { currency: "USDX" }],
    ["opening with letters", { opening: "12a" }],
    ["opening with exponent", { opening: "1e5" }],
    ["date order invalid", { date_order: "ymd" }],
    ["unknown key", { extra: 1 }],
    ["ocr not boolean", { ocr: "yes" }],
    ["account too long", { account: "a".repeat(129) }],
  ])("rejects upload argument: %s", async (_label, extra) => {
    expect(errorCode(await call(new Operations(), "process_upload", upload("s.csv", "a", extra)))).toBe("INVALID_ARGUMENTS");
  });
});

describe("summaries and errors", () => {
  it("summarises a release with counts and assertion total", async () => {
    const item = await call(new Operations(), "process_sample", { opening: "1000.00" });
    expect(resultOf(item)).toMatchObject({ status: "ok", schema_version: "openbooks.v1", assertions: 2, counts: { accounts: 1, transactions: 3, batches: 0 } });
  });

  it("returns a refusal as a result, not an error", async () => {
    runFileMock.mockResolvedValueOnce(refused("s.csv", "UNKNOWN_LAYOUT", "x".repeat(900)));
    const item = await call(new Operations(), "process_sample");
    expect(item.error).toBeUndefined();
    const result = resultOf(item);
    expect(result.status).toBe("refused");
    const failure = result.error as { code: string; message: string };
    expect(failure.code).toBe("UNKNOWN_LAYOUT");
    expect(failure.message).toHaveLength(500);
  });

  it("maps an EngineError to ENGINE_ERROR with the install hint", async () => {
    runFileMock.mockRejectedValueOnce(new EngineError("engine_not_installed", "missing"));
    const item = await call(new Operations(), "process_sample");
    expect(errorCode(item)).toBe("ENGINE_ERROR");
    expect((item.error as { message: string }).message).toContain("install-engine");
  });

  it("maps an unexpected error to ENGINE_ERROR without leaking its message", async () => {
    runFileMock.mockRejectedValueOnce(new Error("secret /home/user/path"));
    const item = await call(new Operations(), "process_sample");
    expect(errorCode(item)).toBe("ENGINE_ERROR");
    expect(JSON.stringify(item)).not.toContain("secret");
  });

  it("reports an unknown operation", async () => {
    expect(errorCode(await call(new Operations(), "does_not_exist"))).toBe("UNKNOWN_OPERATION");
  });

  it("rejects duplicate step ids", async () => {
    const outcome = await new Operations().execute([
      { id: "a", operation: "doctor", arguments: {} },
      { id: "a", operation: "formats", arguments: {} },
    ]);
    expect(outcome.error?.code).toBe("DUPLICATE_STEP");
    expect(outcome.steps).toBeUndefined();
  });
});

describe("invalid arguments per operation", () => {
  const cases: [string, Doc][] = [
    ["doctor", { x: 1 }],
    ["formats", { x: 1 }],
    ["process_sample", { opening: "abc" }],
    ["process_sample", { extra: 1 }],
    ["process_upload", {}],
    ["process_upload", { filename: "a.csv" }],
    ["records", {}],
    ["records", { from_step: "s0" }],
    ["records", { from_step: "s0", collection: "nope" }],
    ["records", { from_step: "s0", collection: "transactions", limit: 11 }],
    ["records", { from_step: "s0", collection: "transactions", limit: 0 }],
    ["records", { from_step: "s0", collection: "transactions", offset: -1 }],
    ["records", { from_step: "s0", collection: "transactions", extra: 1 }],
    ["document", {}],
    ["document", { from_step: "1bad" }],
    ["packages", { details: "yes" }],
    ["packages", { x: 1 }],
    ["capabilities", { details: 1 }],
    ["capabilities", { x: 1 }],
    ["verify_many", {}],
    ["verify_many", { files: [] }],
    ["verify_many", { files: ["a", "b", "c", "d", "e", "f", "g", "h", "i"] }],
    ["verify_many", { files: ["a", "b", "c", "d", "e"], uploads: [1, 2, 3, 4].map((n) => ({ filename: `u${n}.csv`, content_base64: "AAAA" })) }],
    ["verify_many", { files: [""] }],
    ["verify_many", { files: ["a.csv"], extra: 1 }],
  ];

  it.each(cases)("%s rejects %j", async (operation, args) => {
    expect(errorCode(await call(new Operations({ root }), operation, args))).toBe("INVALID_ARGUMENTS");
  });
});

describe("step schema", () => {
  it.each(["a", "step1", "A_b-c", "s".repeat(32)])("accepts id %s", (id) => {
    expect(StepSchema.safeParse({ id, operation: "doctor" }).success).toBe(true);
  });

  it.each(["", "1a", "-a", "a b", "a.b", "s".repeat(33), "a$ref"])("rejects id %j", (id) => {
    expect(StepSchema.safeParse({ id, operation: "doctor" }).success).toBe(false);
  });

  it("rejects unknown step keys and long operation names", () => {
    expect(StepSchema.safeParse({ id: "a", operation: "doctor", extra: 1 }).success).toBe(false);
    expect(StepSchema.safeParse({ id: "a", operation: "x".repeat(41) }).success).toBe(false);
  });

  it("defaults arguments to an empty object", () => {
    expect(StepSchema.parse({ id: "a", operation: "doctor" }).arguments).toEqual({});
  });
});

describe("busy limit", () => {
  it("returns BUSY for a third concurrent call and recovers after release", async () => {
    const releases: (() => void)[] = [];
    runFileMock.mockImplementation(
      (file) => new Promise((resolve) => releases.push(() => resolve(released(basename(file))))),
    );
    const operations = new Operations();
    const first = operations.execute([{ id: "a", operation: "process_sample", arguments: {} }]);
    const second = operations.execute([{ id: "b", operation: "process_sample", arguments: {} }]);
    await vi.waitFor(() => expect(releases).toHaveLength(MAX_CONCURRENT_RUNS));
    const third = await operations.execute([{ id: "c", operation: "process_sample", arguments: {} }]);
    expect(third.error?.code).toBe("BUSY");
    releases.forEach((release) => release());
    await Promise.all([first, second]);
    runFileMock.mockImplementation(async (file) => released(basename(file)));
    const fourth = await operations.execute([{ id: "d", operation: "process_sample", arguments: {} }]);
    expect(fourth.steps).toHaveLength(1);
  });

  it("releases its slot when a step throws", async () => {
    runFileMock.mockRejectedValue(new Error("boom"));
    const operations = new Operations();
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const outcome = await operations.execute([{ id: "a", operation: "process_sample", arguments: {} }]);
      expect(outcome.error).toBeUndefined();
    }
  });
});

describe("response budget and compaction", () => {
  const big = (kilobytes: number): Doc => ({ data: { transactions: Array.from({ length: kilobytes }, (_value, index) => ({ id: `t${index}`, note: "n".repeat(1000) })) } });

  it("replaces an oversized step with RESPONSE_LIMIT", async () => {
    runFileMock.mockResolvedValue(released("s.csv", big(100)));
    const outcome = await new Operations().execute([
      { id: "a", operation: "process_sample", arguments: {} },
      { id: "b", operation: "document", arguments: { from_step: "a" } },
    ]);
    expect(outcome.steps?.[0]?.result).toBeDefined();
    expect(errorCode(outcome.steps?.[1] ?? {})).toBe("RESPONSE_LIMIT");
  });

  it("keeps cumulative output under the budget and still returns later small steps", async () => {
    runFileMock.mockResolvedValue(released("s.csv", big(30)));
    const outcome = await new Operations().execute(
      [
        { id: "a", operation: "process_sample", arguments: {} },
        { id: "d1", operation: "document", arguments: { from_step: "a" } },
        { id: "d2", operation: "document", arguments: { from_step: "a" } },
        { id: "p", operation: "packages", arguments: {} },
      ],
      { stop_on_error: false },
    );
    const steps = outcome.steps ?? [];
    expect(steps[1]?.result).toBeDefined();
    expect(errorCode(steps[2] ?? {})).toBe("RESPONSE_LIMIT");
    expect(steps[3]?.result).toBeDefined();
    expect(Buffer.byteLength(JSON.stringify(outcome))).toBeLessThan(48 * 1024);
  });

  it("drops null values from results", async () => {
    runFileMock.mockResolvedValue(refused("s.csv"));
    const item = await call(new Operations(), "process_sample");
    expect(JSON.stringify(item)).not.toContain("null");
  });

  it("drops next_offset on the last page", async () => {
    const operations = new Operations();
    const outcome = await operations.execute([
      { id: "a", operation: "process_sample", arguments: {} },
      { id: "r", operation: "records", arguments: { from_step: "a", collection: "transactions", limit: 5 } },
    ]);
    expect(resultOf(outcome.steps?.[1] ?? {})).not.toHaveProperty("next_offset");
  });

  it("serialises without whitespace", async () => {
    const outcome = await new Operations().execute([{ id: "a", operation: "capabilities", arguments: {} }]);
    expect(JSON.stringify(outcome)).not.toMatch(/\n| {2}/);
  });
});

describe("records and document", () => {
  const twoSteps = async (args: Doc): Promise<Doc> => {
    const outcome = await new Operations().execute([
      { id: "a", operation: "process_sample", arguments: {} },
      { id: "r", operation: "records", arguments: { from_step: "a", ...args } },
    ]);
    return outcome.steps?.[1] ?? {};
  };

  it("pages transactions with a next offset", async () => {
    const result = resultOf(await twoSteps({ collection: "transactions", limit: 2 }));
    expect(result).toMatchObject({ collection: "transactions", total: 3, next_offset: 2 });
    expect(result.items).toHaveLength(2);
  });

  it("returns the final page without a next offset", async () => {
    const result = resultOf(await twoSteps({ collection: "transactions", limit: 2, offset: 2 }));
    expect(result.items).toEqual([{ id: "t3" }]);
    expect(result).not.toHaveProperty("next_offset");
  });

  it("filters by id prefix", async () => {
    const result = resultOf(await twoSteps({ collection: "transactions", prefix: "t2" }));
    expect(result.items).toEqual([{ id: "t2" }]);
  });

  it("reads evidence entries by key prefix", async () => {
    const result = resultOf(await twoSteps({ collection: "evidence", prefix: "t1" }));
    expect(result.items).toEqual([{ key: "t1.amount", page: 1 }]);
  });

  it("reads assertions from the top level", async () => {
    expect(resultOf(await twoSteps({ collection: "assertions" })).total).toBe(2);
  });

  it.each(["accounts", "parties", "batches", "transactions", "claims", "assertions", "evidence"])("serves collection %s", async (collection) => {
    const result = resultOf(await twoSteps({ collection }));
    expect(result.collection).toBe(collection);
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("refuses records for a refused document", async () => {
    runFileMock.mockResolvedValueOnce(refused("s.csv"));
    const item = await twoSteps({ collection: "transactions" });
    expect(errorCode(item)).toBe("DOCUMENT_REFUSED");
  });

  it("reports a missing source step", async () => {
    const item = await call(new Operations(), "records", { from_step: "ghost", collection: "transactions" });
    expect(errorCode(item)).toBe("MISSING_DOCUMENT");
  });

  it("does not treat a non-processing step as a document", async () => {
    const outcome = await new Operations().execute([
      { id: "d", operation: "capabilities", arguments: {} },
      { id: "r", operation: "document", arguments: { from_step: "d" } },
    ]);
    expect(errorCode(outcome.steps?.[1] ?? {})).toBe("MISSING_DOCUMENT");
  });

  it("returns the full document", async () => {
    const outcome = await new Operations().execute([
      { id: "a", operation: "process_sample", arguments: {} },
      { id: "d", operation: "document", arguments: { from_step: "a" } },
    ]);
    expect(resultOf(outcome.steps?.[1] ?? {}).status).toBe("ok");
  });
});

describe("$ref substitution", () => {
  const withSource = async (args: Doc, source: Doc = {}, options: { stop_on_error?: boolean } = {}) => {
    runFileMock.mockResolvedValue(released("s.csv", source));
    const outcome = await new Operations().execute(
      [
        { id: "s1", operation: "process_sample", arguments: {} },
        { id: "s2", operation: "process_upload", arguments: { ...upload(), ...args } },
      ],
      options,
    );
    return outcome.steps?.[1] ?? {};
  };

  it("substitutes a string from an earlier document", async () => {
    await withSource({ opening: { $ref: "s1.data.opening" } });
    expect(runFileMock.mock.calls[1]?.[1]).toMatchObject({ opening: "1000.00" });
  });

  it("indexes into arrays", async () => {
    await withSource({ account: { $ref: "s1.data.accounts.0.id" } });
    expect(runFileMock.mock.calls[1]?.[1]).toMatchObject({ account: "acc1" });
  });

  it("reads a field of a non-document step output", async () => {
    runFileMock.mockResolvedValue(released("s.csv"));
    const outcome = await new Operations().execute([
      { id: "p", operation: "packages", arguments: {} },
      { id: "c", operation: "process_upload", arguments: { ...upload(), account: { $ref: "p.count" } } },
    ]);
    expect(errorCode(outcome.steps?.[1] ?? {})).toBe("INVALID_ARGUMENTS");
  });

  it("resolves refs nested inside arrays and objects", async () => {
    runFileMock.mockResolvedValue(released("s.csv"));
    const outcome = await new Operations({ root }).execute([
      { id: "s1", operation: "process_sample", arguments: {} },
      { id: "s2", operation: "verify_many", arguments: { files: [{ $ref: "s1.file" }], opening: { $ref: "s1.data.opening" } } },
    ]);
    expect(resultOf(outcome.steps?.[1] ?? {}).total).toBe(1);
  });

  it.each([
    ["unknown step", "nope.data"],
    ["empty reference", ""],
    ["only a dot", "."],
    ["missing key", "s1.data.missing"],
    ["proto key", "s1.__proto__"],
    ["proto key inside path", "s1.data.__proto__.x"],
    ["constructor key", "s1.data.constructor"],
    ["prototype key", "s1.data.prototype"],
    ["array index out of range", "s1.data.accounts.99"],
    ["non-numeric array index", "s1.data.accounts.x"],
    ["path through a primitive", "s1.data.opening.length"],
    ["later step", "s2.data"],
    ["path deeper than the limit", `s1.${Array.from({ length: 17 }, () => "a").join(".")}`],
  ])("rejects bad ref: %s", async (_label, reference) => {
    const item = await withSource({ account: { $ref: reference } });
    expect(errorCode(item)).toBe("BAD_REF");
    expect(runFileMock).toHaveBeenCalledTimes(1);
  });

  it("rejects a referenced value above the size limit", async () => {
    const item = await withSource({ account: { $ref: "s1.data.blob" } }, { data: { blob: "x".repeat(5000) } });
    expect(errorCode(item)).toBe("BAD_REF");
  });

  it("rejects a ref to a step that failed", async () => {
    const outcome = await new Operations().execute(
      [
        { id: "bad", operation: "does_not_exist", arguments: {} },
        { id: "use", operation: "process_sample", arguments: { opening: { $ref: "bad.data" } } },
      ],
      { stop_on_error: false },
    );
    expect(errorCode(outcome.steps?.[1] ?? {})).toBe("BAD_REF");
  });

  it("rejects arguments nested beyond the depth limit", async () => {
    let nested: unknown = "leaf";
    for (let level = 0; level < 20; level += 1) nested = { k: nested };
    const item = await withSource({ account: nested });
    expect(errorCode(item)).toBe("BAD_REF");
  });

  it("treats a $ref with extra keys as a literal object", async () => {
    expect(errorCode(await withSource({ account: { $ref: "s1.file", other: 1 } }))).toBe("INVALID_ARGUMENTS");
  });

  it("treats a non-string $ref as a literal object", async () => {
    expect(errorCode(await withSource({ account: { $ref: 5 } }))).toBe("INVALID_ARGUMENTS");
  });

  it("never evaluates plain strings that look like references", async () => {
    expect(errorCode(await withSource({ opening: "s1.data.opening" }))).toBe("INVALID_ARGUMENTS");
  });

  it("does not pollute Object.prototype", async () => {
    await withSource({ account: { $ref: "s1.__proto__.polluted" } });
    expect(Object.hasOwn(Object.prototype, "polluted")).toBe(false);
  });
});

describe("parallel execution", () => {
  const uploads = (count: number) => Array.from({ length: count }, (_value, index) => ({ id: `u${index}`, operation: "process_upload", arguments: upload(`f${index}.csv`) }));

  const trackConcurrency = () => {
    const state = { active: 0, peak: 0 };
    runFileMock.mockImplementation(async (file) => {
      state.active += 1;
      state.peak = Math.max(state.peak, state.active);
      const index = Number(/f(\d+)\.csv/.exec(basename(file))?.[1] ?? 0);
      await sleep(40 - index * 8);
      state.active -= 1;
      return released(basename(file));
    });
    return state;
  };

  it("preserves input order although completion order differs", async () => {
    trackConcurrency();
    const outcome = await new Operations().execute(uploads(4), { parallel: true });
    expect(outcome.steps?.map((step) => step.id)).toEqual(["u0", "u1", "u2", "u3"]);
    expect(outcome.steps?.map((step) => resultOf(step).file)).toEqual(["f0.csv", "f1.csv", "f2.csv", "f3.csv"]);
  });

  it("never exceeds MAX_CONCURRENT_RUNS", async () => {
    const state = trackConcurrency();
    await new Operations().execute(uploads(MAX_STEPS), { parallel: true });
    expect(state.peak).toBe(MAX_CONCURRENT_RUNS);
  });

  it("runs sequentially by default", async () => {
    const state = trackConcurrency();
    await new Operations().execute(uploads(4));
    expect(state.peak).toBe(1);
  });

  it("rejects parallel steps that use from_step", async () => {
    const outcome = await new Operations().execute(
      [
        { id: "a", operation: "process_sample", arguments: {} },
        { id: "b", operation: "records", arguments: { from_step: "a", collection: "transactions" } },
      ],
      { parallel: true },
    );
    expect(outcome.error?.code).toBe("PARALLEL_DEPENDENCY");
    expect(runFileMock).not.toHaveBeenCalled();
  });

  it("rejects parallel steps that use $ref, even when nested", async () => {
    const outcome = await new Operations().execute(
      [
        { id: "a", operation: "process_sample", arguments: {} },
        { id: "b", operation: "verify_many", arguments: { files: [{ $ref: "a.file" }] } },
      ],
      { parallel: true },
    );
    expect(outcome.error?.code).toBe("PARALLEL_DEPENDENCY");
  });

  it("halts after the failing chunk when stop_on_error is true", async () => {
    const outcome = await new Operations().execute(
      [
        { id: "a", operation: "nope", arguments: {} },
        { id: "b", operation: "doctor", arguments: {} },
        { id: "c", operation: "doctor", arguments: {} },
      ],
      { parallel: true },
    );
    expect(errorCode(outcome.steps?.[0] ?? {})).toBe("UNKNOWN_OPERATION");
    expect(outcome.steps?.[1]?.result).toBeDefined();
    expect(errorCode(outcome.steps?.[2] ?? {})).toBe("SKIPPED");
  });
});

describe("stop_on_error", () => {
  const batch = [
    { id: "a", operation: "doctor", arguments: {} },
    { id: "b", operation: "nope", arguments: {} },
    { id: "c", operation: "formats", arguments: {} },
    { id: "d", operation: "formats", arguments: {} },
  ];

  it("defaults to true and skips the remaining steps", async () => {
    const outcome = await new Operations().execute(batch);
    expect(outcome.steps?.map((step) => errorCode(step))).toEqual([undefined, "UNKNOWN_OPERATION", "SKIPPED", "SKIPPED"]);
  });

  it("continues when false", async () => {
    const outcome = await new Operations().execute(batch, { stop_on_error: false });
    expect(outcome.steps?.map((step) => errorCode(step))).toEqual([undefined, "UNKNOWN_OPERATION", undefined, undefined]);
  });

  it("does not treat a refusal as an error", async () => {
    runFileMock.mockResolvedValueOnce(refused("s.csv"));
    const outcome = await new Operations().execute([
      { id: "a", operation: "process_sample", arguments: {} },
      { id: "b", operation: "process_sample", arguments: {} },
    ]);
    expect(outcome.steps?.map((step) => resultOf(step).status)).toEqual(["refused", "ok"]);
  });

  it("skips after an invalid-argument failure", async () => {
    const outcome = await new Operations().execute([
      { id: "a", operation: "process_sample", arguments: { opening: "bad" } },
      { id: "b", operation: "doctor", arguments: {} },
    ]);
    expect(errorCode(outcome.steps?.[1] ?? {})).toBe("SKIPPED");
  });
});

describe("verify_many", () => {
  it("returns one compact status per file and per upload", async () => {
    runFileMock.mockImplementation(async (file) => (basename(file) === "b.csv" ? refused("b.csv", "UNKNOWN_LAYOUT") : released(basename(file))));
    const item = await call(new Operations({ root }), "verify_many", {
      files: ["a.csv", "sub/b.csv", "missing.csv"],
      uploads: [{ filename: "up.csv", content_base64: encode("x,y\n") }, { filename: "bad.exe", content_base64: encode("x") }],
    });
    const result = resultOf(item);
    expect(result).toMatchObject({ total: 5, ok: 2, refused: 1, error: 2 });
    expect(result.files).toEqual([
      { name: "a.csv", status: "ok", rows: 3, assertions: 2 },
      { name: "sub/b.csv", status: "refused", code: "UNKNOWN_LAYOUT" },
      { name: "missing.csv", status: "error", code: "INVALID_PATH" },
      { name: "up.csv", status: "ok", rows: 3, assertions: 2 },
      { name: "bad.exe", status: "error", code: "UNSUPPORTED_INPUT" },
    ]);
  });

  it("reports local files as errors when no root is configured", async () => {
    const result = resultOf(await call(new Operations(), "verify_many", { files: ["a.csv"] }));
    expect(result.files).toEqual([{ name: "a.csv", status: "error", code: "INVALID_PATH" }]);
  });

  it("contains containment failures per file", async () => {
    const result = resultOf(await call(new Operations({ root }), "verify_many", { files: ["../a.csv", "escape/secret.csv", "a.csv"] }));
    expect(result).toMatchObject({ ok: 1, error: 2 });
    expect(runFileMock).toHaveBeenCalledOnce();
  });

  it("maps engine failures to ENGINE_ERROR for that file only", async () => {
    runFileMock.mockImplementation(async (file) => {
      if (basename(file) === "a.csv") throw new EngineError("timeout", "slow");
      return released(basename(file));
    });
    const result = resultOf(await call(new Operations({ root }), "verify_many", { files: ["a.csv", "sub/b.csv"] }));
    expect(result.files).toMatchObject([{ status: "error", code: "ENGINE_ERROR" }, { status: "ok" }]);
  });

  it("accepts the maximum of eight items", async () => {
    const files = Array.from({ length: MAX_STEPS }, () => "a.csv");
    expect(resultOf(await call(new Operations({ root }), "verify_many", { files })).total).toBe(MAX_STEPS);
  });

  it("limits concurrent engine runs", async () => {
    let active = 0;
    let peak = 0;
    runFileMock.mockImplementation(async (file) => {
      active += 1;
      peak = Math.max(peak, active);
      await sleep(10);
      active -= 1;
      return released(basename(file));
    });
    await call(new Operations({ root }), "verify_many", { files: Array.from({ length: 6 }, () => "a.csv") });
    expect(peak).toBeLessThanOrEqual(MAX_CONCURRENT_RUNS);
  });

  it("applies shared processing options to every file", async () => {
    await call(new Operations({ root }), "verify_many", { files: ["a.csv", "sub/b.csv"], currency: "EUR" });
    expect(runFileMock.mock.calls.map((entry) => entry[1])).toEqual([expect.objectContaining({ currency: "EUR" }), expect.objectContaining({ currency: "EUR" })]);
  });
});

describe("packages", () => {
  it("returns only counts by default", async () => {
    const result = resultOf(await call(new Operations(), "packages"));
    expect(result).toEqual({ count: WORKSPACE_PACKAGES.length, engine_available: true });
  });

  it("lists every workspace package with name, version and role when details is true", async () => {
    const result = resultOf(await call(new Operations(), "packages", { details: true }));
    const packages = result.packages as Doc[];
    expect(packages).toHaveLength(result.count as number);
    for (const entry of packages) {
      expect(entry).toEqual({ name: expect.stringMatching(/^@lumeo_hq\//), version: expect.stringMatching(/^\d+\.\d+\.\d+/), role: expect.any(String) });
    }
  });

  it("matches the package.json files on disk", async () => {
    const { readdirSync, readFileSync } = await import("node:fs");
    const base = join(root, "..", "..", "..");
    void base;
    const here = join(import.meta.dirname, "..", "..");
    const onDisk = readdirSync(here, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && entry.name !== "node_modules")
      .flatMap((entry) => {
        try {
          const manifest = JSON.parse(readFileSync(join(here, entry.name, "package.json"), "utf8")) as { name: string; version: string };
          return [`${manifest.name}@${manifest.version}`];
        } catch {
          return [];
        }
      })
      .sort();
    expect(WORKSPACE_PACKAGES.map((entry) => `${entry.name}@${entry.version}`).sort()).toEqual(onDisk);
  });

  it("includes the Python engine version", async () => {
    const engine = resultOf(await call(new Operations(), "packages", { details: true })).engine as Doc;
    expect(engine).toMatchObject({ name: "openbooks", version: "9.9.9", schema_version: "openbooks.v1", layout_api: 1 });
  });

  it("reports an unavailable engine", async () => {
    findEngineMock.mockRejectedValue(new EngineError("engine_not_installed", "missing"));
    const result = resultOf(await call(new Operations(), "packages", { details: true }));
    expect(result.engine_available).toBe(false);
    expect(result.engine).toEqual({ available: false });
  });
});

describe("capabilities", () => {
  it("returns derived counts by default", async () => {
    const result = resultOf(await call(new Operations(), "capabilities"));
    expect(result).toEqual({
      engine_available: true,
      operations: 9,
      tools: TOOL_NAMES.length,
      resources: RESOURCE_URIS.length,
      prompts: PROMPT_NAMES.length,
      extensions: EXTENSIONS.length,
      refusal_codes: Object.keys(REFUSAL_CODES).length,
      collections: 7,
      statuses: 2,
      layouts: 3,
      known_layouts: 2,
      frontends: 2,
    });
  });

  it("counts process_file when a root is set", async () => {
    expect(resultOf(await call(new Operations({ root }), "capabilities")).operations).toBe(10);
  });

  it("reports zero engine counts when the engine is missing", async () => {
    findEngineMock.mockRejectedValue(new EngineError("engine_not_installed", "missing"));
    const result = resultOf(await call(new Operations(), "capabilities"));
    expect(result).toMatchObject({ engine_available: false, layouts: 0, known_layouts: 0, frontends: 0 });
  });

  it("has list lengths that equal the counts", async () => {
    const result = resultOf(await call(new Operations({ root }), "capabilities", { details: true }));
    const pairs: [string, string][] = [
      ["operation_names", "operations"], ["tool_names", "tools"], ["resource_uris", "resources"], ["prompt_names", "prompts"],
      ["extension_list", "extensions"], ["refusal_code_list", "refusal_codes"], ["collection_list", "collections"],
      ["status_list", "statuses"], ["layout_ids", "layouts"], ["known_layout_list", "known_layouts"], ["frontend_list", "frontends"],
    ];
    for (const [list, count] of pairs) expect((result[list] as unknown[]).length).toBe(result[count]);
  });

  it("lists the new operations", async () => {
    const names = resultOf(await call(new Operations(), "capabilities", { details: true })).operation_names as string[];
    expect(names).toEqual(expect.arrayContaining(["packages", "capabilities", "verify_many"]));
  });

  it("omits lists in the summary", async () => {
    expect(resultOf(await call(new Operations(), "capabilities"))).not.toHaveProperty("operation_names");
  });
});

describe("doctor and formats", () => {
  it("is healthy when the self test releases", async () => {
    const result = resultOf(await call(new Operations(), "doctor"));
    expect(result).toMatchObject({ healthy: true, engine: { available: true, version: "9.9.9" }, document_frontend: true, self_test: { status: "ok" } });
  });

  it("is unhealthy when the self test is refused", async () => {
    runFileMock.mockResolvedValue(refused("statement.csv"));
    expect(resultOf(await call(new Operations(), "doctor"))).toMatchObject({ healthy: false, self_test: { status: "refused" } });
  });

  it("is unhealthy when the self test throws", async () => {
    runFileMock.mockRejectedValue(new TypeError("x"));
    expect(resultOf(await call(new Operations(), "doctor"))).toMatchObject({ healthy: false, self_test: { status: "failed", reason: "TypeError" } });
  });

  it("gives the install fix when the engine is missing", async () => {
    findEngineMock.mockRejectedValue(new EngineError("engine_not_installed", "missing"));
    const result = resultOf(await call(new Operations(), "doctor"));
    expect(result).toMatchObject({ healthy: false, engine: { available: false }, self_test: { status: "skipped" } });
    expect(result.fix).toContain("install-engine");
  });

  it("reports whether local files are enabled", async () => {
    expect(resultOf(await call(new Operations({ root }), "doctor")).local_files_enabled).toBe(true);
    expect(resultOf(await call(new Operations(), "doctor")).local_files_enabled).toBe(false);
  });

  it("rethrows unexpected discovery failures as ENGINE_ERROR", async () => {
    findEngineMock.mockRejectedValue(new TypeError("boom"));
    expect(errorCode(await call(new Operations(), "doctor"))).toBe("ENGINE_ERROR");
  });

  it("formats lists layouts and extensions", async () => {
    const result = resultOf(await call(new Operations(), "formats"));
    expect(result.layouts).toEqual(ENGINE.info.layouts);
    expect(result.extensions).toEqual([...EXTENSIONS]);
  });

  it("formats fails with ENGINE_UNAVAILABLE when the engine is missing", async () => {
    findEngineMock.mockRejectedValue(new EngineError("engine_not_installed", "missing"));
    expect(errorCode(await call(new Operations(), "formats"))).toBe("ENGINE_UNAVAILABLE");
  });
});

describe("search", () => {
  it.each([
    ["verify many files", "verify_many"],
    ["packages npm", "packages"],
    ["capabilities", "capabilities"],
    ["doctor", "doctor"],
    ["formats", "formats"],
    ["upload base64", "process_upload"],
    ["records page", "records"],
    ["sample", "process_sample"],
  ])("finds %s", (query, expected) => {
    const names = new Operations().search(query, false).operations.map((item) => item.name);
    expect(names).toContain(expected);
  });

  it("returns every operation for an empty query", () => {
    expect(new Operations().search("", false).operations).toHaveLength(9);
    expect(new Operations({ root }).search("", false).operations).toHaveLength(10);
  });

  it("returns nothing for a query with no match", () => {
    expect(new Operations().search("zzzzzz", false).operations).toEqual([]);
  });

  it("ranks the strongest match first", () => {
    expect(new Operations().search("verify many files", false).operations[0]?.name).toBe("verify_many");
  });

  it("includes argument schemas only when details is true", () => {
    const plain = new Operations().search("packages", false).operations[0];
    const detailed = new Operations().search("packages", true).operations.find((item) => item.name === "packages");
    expect(plain).not.toHaveProperty("arguments");
    expect(detailed?.arguments).toMatchObject({ type: "object" });
  });

  it("reports the step limit", () => {
    expect(new Operations().search("", false).max_steps).toBe(MAX_STEPS);
  });
});
