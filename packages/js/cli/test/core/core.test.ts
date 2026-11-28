import { existsSync, readdirSync, readFileSync, statSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { clearEngineCache, EngineError, isReleased, runFile, runFiles, runJobs } from "../../src/core/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../../../..");
const venvPython = join(repo, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const realPython = process.env.OPENBOOKS_PYTHON ?? (existsSync(venvPython) ? venvPython : undefined);
const fake = [process.execPath, join(here, "fake-engine.mjs")];

describe("proof output and mixed jobs", () => {
  it("bounds serialized documents independently of subprocess output", async () => {
    await expect(runFile(file("limited-output.csv", BANK), { python: fake, maxDocumentBytes: 8 }))
      .rejects.toMatchObject({ kind: "bad_output" });
  });

  it("uses the typed protocol error when engine-info is malformed", async () => {
    clearEngineCache();
    process.env.FAKE_MODE = "null_info";
    await expect(runFile(file("bad-info.csv", BANK), { python: fake }))
      .rejects.toMatchObject({ kind: "bad_output" });
  });
});

const sharedDir = join(repo, "packages/py/openbooks/tests/fixtures/shared");
const MT940 = readFileSync(join(sharedDir, "mt940_balanced.sta"), "utf8");
const MT940_TAMPERED = readFileSync(join(sharedDir, "mt940_tampered_closing.sta"), "utf8");
const BANK = "Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,Pay,,5.00,1005.00\n";
const STRIPE = "balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n";
const work = mkdtempSync(join(tmpdir(), "ob-js-test-"));
const file = (name: string, text: string) => { const p = join(work, name); writeFileSync(p, text); return p; };
const scratch = mkdtempSync(join(tmpdir(), "ob-scratch-"));
for (const k of ["TMPDIR", "TMP", "TEMP"]) process.env[k] = scratch;
const leftovers = () => readdirSync(scratch).length;

afterEach(() => {
  if (process.env.FAKE_MODE) clearEngineCache();
  delete process.env.FAKE_MODE;
});

describe.skipIf(!realPython)("with the real engine", () => {
  const opts = { python: realPython!, currency: "INR", dateOrder: "dmy" as const, opening: "1000.00" };
  const mt = { python: realPython!, currency: "INR", dateOrder: "dmy" as const };

  it("keeps per-file document options and preserves ordered decisions", async () => {
    const outcomes = [];
    for await (const result of runJobs([
      { file: file("mixed-caller.csv", BANK), options: { opening: "1000.00" } },
      { file: file("mixed-job.sta", MT940), options: {} },
    ], mt)) outcomes.push(result.kind === "refused" ? result.code : result.kind);
    expect(outcomes).toEqual(["BALANCE_MISMATCH", "released"]);
  });

  it("returns a released document with typed, validated content", async () => {
    const r = await runFile(file("a.sta", MT940), mt);
    expect(r.kind).toBe("released");
    if (!isReleased(r)) return;
    const t = r.document.data.transactions[0];
    expect(t.amount?.amount).toBe("500.00");
    expect(r.document.file.layout_version).toBe("mt940.v1");
    expect(r.document.assertions.some((a) => a.independent)).toBe(true);
  });

  it("refuses a caller-opened CSV with BALANCE_MISMATCH instead of releasing it", async () => {
    const r = await runFile(file("caller.csv", BANK), opts);
    expect(r.kind).toBe("refused");
    if (r.kind === "refused") expect(r.code).toBe("BALANCE_MISMATCH");
  });

  it("returns a refusal as a value, not an exception", async () => {
    const r = await runFile(file("b.csv", BANK.replace("1005.00", "1005.01")), opts);
    expect(r.kind).toBe("refused");
    if (r.kind === "refused") {
      expect(r.code).toBe("BALANCE_MISMATCH");
      expect(r.document.data).toBeNull();
      expect(r.internal).toBe(false);
    }
  });

  it("runs several files in one call and keeps their order", async () => {
    const rs = await runFiles([file("c1.sta", MT940), file("c2.csv", STRIPE), file("c3.csv", "a,b\n1,2\n")], mt);
    expect(rs.map((r) => (r.kind === "released" ? r.document.file.layout_version : r.code))).toEqual(["mt940.v1", "stripe_balance.v1", "UNKNOWN_LAYOUT"]);
  });

  it("withholds a document that proves out under a layout the caller did not accept", async () => {
    const r = await runFile(file("d.csv", STRIPE), { ...opts, accept: ["bank_csv.v1"] });
    expect(r.kind).toBe("refused");
    if (r.kind === "refused") { expect(r.code).toBe("UNKNOWN_LAYOUT"); expect(r.restricted).toBe(true); expect(r.message).toContain("stripe_balance.v1"); }
  });

  it("handles a path with spaces and non-ASCII characters", async () => {
    const r = await runFile(file("statement é 1.sta", MT940), mt);
    expect(r.kind).toBe("released");
  });

  it("refuses a missing input as an input error before starting the engine", async () => {
    await expect(runFile(join(work, "nope.csv"), opts)).rejects.toMatchObject({ kind: "input" });
  });

  it("rejects an opening balance that is not a plain decimal string", async () => {
    await expect(runFile(file("e.csv", BANK), { ...opts, opening: "1e3" })).rejects.toMatchObject({ kind: "input" });
  });

  it("cleans up its temporary directory", async () => {
    const before = leftovers();
    await runFile(file("f.csv", BANK), opts);
    expect(leftovers()).toBe(before);
  });

  const bytes = (n: number, k: number) => Buffer.from(Array.from({ length: n }, (_, i) => (i * k) % 256));
  const hostile: Array<[string, string, Buffer | string]> = [
    ["an empty file", "h1.csv", ""],
    ["one byte", "h2.csv", "x"],
    ["a NUL byte", "h3.csv", "Date,Narration\u0000,Deposit Amt\n"],
    ["random bytes", "h4.csv", bytes(4096, 37)],
    ["only newlines", "h5.csv", "\n".repeat(5000)],
    ["a two-megabyte line", "h6.csv", "Date," + "a".repeat(2_000_000) + "\n"],
    ["a header and nothing else", "h7.csv", "Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n"],
    ["a PDF that is not one", "h8.pdf", bytes(2048, 13)],
    ["a workbook that is not one", "h9.xlsx", bytes(2048, 7)],
    ["a PNG that is not one", "h10.png", bytes(2048, 11)],
    ["an unsupported type", "h11.docx", "PK"],
  ];
  it.each(hostile)("refuses %s as a typed refusal, not a crash", async (_what, name, content) => {
    const p = join(work, name);
    writeFileSync(p, content);
    const r = await runFile(p, opts).catch((e: unknown) => e);
    if (r instanceof EngineError) {
      expect(r.kind).toBe("engine_fault");
      expect(r.message).toMatch(/pip install '?openbooks(\[scan\])?'?/);
      return;
    }
    expect(r).toMatchObject({ kind: "refused", internal: false });
    expect(["UNKNOWN_LAYOUT", "PARSE_ERROR", "UNSUPPORTED_INPUT"]).toContain((r as { code: string }).code);
  });

  it("accepts a lower-case currency code and reads the same statement", async () => {
    const r = await runFile(file("lc.sta", MT940), { ...mt, currency: "inr" });
    expect(r.kind).toBe("released");
    if (isReleased(r)) expect(r.document.data.transactions[0].amount?.currency).toBe("INR");
  });

  it("keeps the order and the outcome of every file when a bad one is in the middle", async () => {
    const rs = await runFiles([file("m1.sta", MT940), file("m2.csv", "\u0000junk"), file("m3.sta", MT940_TAMPERED), file("m4.sta", MT940)], mt);
    expect(rs.map((r) => (r.kind === "released" ? "ok" : r.code))).toEqual(["ok", "UNSUPPORTED_INPUT", "BALANCE_MISMATCH", "ok"]);
  });

  it("gives the same document for the same file every time", async () => {
    const p = file("same.csv", BANK);
    const [a, b, c] = await Promise.all([runFile(p, opts), runFile(p, opts), runFile(p, opts)]);
    expect(JSON.stringify((a as any).document)).toBe(JSON.stringify((b as any).document));
    expect(JSON.stringify((b as any).document)).toBe(JSON.stringify((c as any).document));
  });

  it("copes with many files at once", async () => {
    const paths = Array.from({ length: 12 }, (_, i) => file(`bulk${i}.sta`, i % 4 === 3 ? MT940_TAMPERED : MT940));
    const rs = await runFiles(paths, mt);
    expect(rs.filter((r) => r.kind === "released")).toHaveLength(9);
    expect(rs.filter((r) => r.kind === "refused")).toHaveLength(3);
  });

  it("does not modify the input file", async () => {
    const p = file("untouched.csv", BANK);
    const before = [readFileSync(p, "utf8"), statSync(p).mtimeMs];
    await runFile(p, opts);
    expect([readFileSync(p, "utf8"), statSync(p).mtimeMs]).toEqual(before);
  });
});

describe("when the environment is wrong", () => {
  it("says so when there is no such Python", async () => {
    await expect(runFile(file("g.csv", BANK), { python: "definitely-not-a-python-xyz" })).rejects.toMatchObject({ kind: "python_not_found" });
  });

  it("says so when Python is there but the engine is not installed", async () => {
    process.env.FAKE_MODE = "no_module";
    const e = await runFile(file("h.csv", BANK), { python: fake }).catch((x: unknown) => x);
    expect(e).toBeInstanceOf(EngineError);
    expect(e).toMatchObject({ kind: "engine_not_installed" });
    expect((e as EngineError).hint).toContain("pip install");
  });

  it("refuses an engine that speaks a different contract", async () => {
    process.env.FAKE_MODE = "old";
    await expect(runFile(file("i.csv", BANK), { python: fake })).rejects.toMatchObject({ kind: "engine_version" });
  });
});

describe("when the engine misbehaves, that is an error and never a refusal", () => {
  it("treats a crash (exit 3) as an engine fault and shows the engine's message", async () => {
    process.env.FAKE_MODE = "crash";
    const e = await runFile(file("j.csv", BANK), { python: fake }).catch((x: unknown) => x);
    expect(e).toMatchObject({ kind: "engine_fault" });
    expect((e as Error).message).toContain("boom");
  });

  it("treats non-JSON output as bad output", async () => {
    process.env.FAKE_MODE = "garbage";
    await expect(runFile(file("k.csv", BANK), { python: fake })).rejects.toMatchObject({ kind: "bad_output" });
  });

  it("rejects output that does not match the contract", async () => {
    process.env.FAKE_MODE = "bad_doc";
    await expect(runFile(file("l.csv", BANK), { python: fake })).rejects.toMatchObject({ kind: "bad_output" });
  });

  it("rejects an output file that belongs to a different input", async () => {
    process.env.FAKE_MODE = "wrong_file";
    await expect(runFile(file("m.csv", BANK), { python: fake })).rejects.toMatchObject({ kind: "bad_output" });
  });

  it.each(["wrong_hash", "external_path", "bad_line"])("rejects a mismatched or malformed result (%s)", async (mode) => {
    process.env.FAKE_MODE = mode;
    await expect(runFile(file(`${mode}.csv`, BANK), { python: fake })).rejects.toMatchObject({ kind: "bad_output" });
  });

  it("keeps results separate for inputs with identical bytes", async () => {
    const paths = [file("same-bytes.csv", BANK), file("same-bytes.txt", BANK)];
    const results = await runFiles(paths, { python: fake });
    expect(results).toMatchObject([
      { kind: "refused", file: "same-bytes.csv", message: "same-bytes.csv" },
      { kind: "refused", file: "same-bytes.txt", message: "same-bytes.txt" },
    ]);
  });

  it("rejects a pre-aborted run before accessing input or Python", async () => {
    await expect(runFile(join(work, "missing.csv"), { python: "missing", signal: AbortSignal.abort() }))
      .rejects.toMatchObject({ kind: "aborted" });
  });

  it("rejects a timer outside Node's supported range instead of timing out after 1 ms", async () => {
    await expect(runFile(file("overflow.csv", BANK), { python: fake, runTimeoutMs: 2 ** 31 }))
      .rejects.toMatchObject({ kind: "input" });
  });

  it("stops a hung engine at the timeout and cleans up", async () => {
    process.env.FAKE_MODE = "hang";
    const before = leftovers();
    const t = Date.now();
    await expect(runFile(file("n.csv", BANK), { python: fake, runTimeoutMs: 800 })).rejects.toMatchObject({ kind: "timeout" });
    expect(Date.now() - t).toBeLessThan(15_000);
    expect(leftovers()).toBe(before);
  });

  it("stops an engine that floods its output", async () => {
    process.env.FAKE_MODE = "noisy";
    await expect(runFile(file("o.csv", BANK), { python: fake, runTimeoutMs: 20_000, maxOutputBytes: 1_000_000 })).rejects.toMatchObject({ kind: "engine_fault" });
  });

  it("honours an AbortSignal", async () => {
    process.env.FAKE_MODE = "hang";
    const ac = new AbortController();
    setTimeout(() => ac.abort(), 500);
    await expect(runFile(file("p.csv", BANK), { python: fake, signal: ac.signal })).rejects.toMatchObject({ kind: "aborted" });
  });
});
