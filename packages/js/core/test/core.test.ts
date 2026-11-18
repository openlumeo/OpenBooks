import { existsSync, readdirSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { clearEngineCache, EngineError, isReleased, runFile, runFiles } from "../src/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../../..");
const venvPython = join(repo, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const realPython = process.env.OPENBOOKS_PYTHON ?? (existsSync(venvPython) ? venvPython : undefined);
const fake = [process.execPath, join(here, "fake-engine.mjs")];

const BANK = "Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,Pay,,5.00,1005.00\n";
const STRIPE = "balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n";
const work = mkdtempSync(join(tmpdir(), "ob-js-test-"));
const file = (name: string, text: string) => { const p = join(work, name); writeFileSync(p, text); return p; };
// The engine wrapper creates its scratch directory under os.tmpdir(). Point that at a directory only this test file uses, so
// "nothing left behind" is checked exactly and cannot be disturbed by other test files running in parallel.
const scratch = mkdtempSync(join(tmpdir(), "ob-scratch-"));
for (const k of ["TMPDIR", "TMP", "TEMP"]) process.env[k] = scratch;
const leftovers = () => readdirSync(scratch).length;

afterEach(() => { delete process.env.FAKE_MODE; clearEngineCache(); });

describe.skipIf(!realPython)("with the real engine", () => {
  const opts = { python: realPython!, currency: "INR", opening: "1000.00" };

  it("returns a released document with typed, validated content", async () => {
    const r = await runFile(file("a.csv", BANK), opts);
    expect(r.kind).toBe("released");
    if (!isReleased(r)) return;
    const t = r.document.data.transactions[0];
    expect(t.amount?.amount).toBe("5.00"); // a string: money is never a JS number
    expect(r.document.file.layout_version).toBe("bank_csv.v1");
    expect(r.document.assertions.some((a) => a.independent)).toBe(true);
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
    const rs = await runFiles([file("c1.csv", BANK), file("c2.csv", STRIPE), file("c3.csv", "a,b\n1,2\n")], opts);
    expect(rs.map((r) => (r.kind === "released" ? r.document.file.layout_version : r.code))).toEqual(["bank_csv.v1", "stripe_balance.v1", "UNKNOWN_LAYOUT"]);
  });

  it("withholds a document that proves out under a layout the caller did not accept", async () => {
    const r = await runFile(file("d.csv", STRIPE), { ...opts, accept: ["bank_csv.v1"] });
    expect(r.kind).toBe("refused");
    if (r.kind === "refused") { expect(r.code).toBe("UNKNOWN_LAYOUT"); expect(r.restricted).toBe(true); expect(r.message).toContain("stripe_balance.v1"); }
  });

  it("handles a path with spaces and non-ASCII characters", async () => {
    const r = await runFile(file("statement é 1.csv", BANK), opts);
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
