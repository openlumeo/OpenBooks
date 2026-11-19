import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { clearEngineCache, findEngine } from "@lumeo_hq/openbooks-core";
import * as gateways from "@lumeo_hq/openbooks-gateways";
import * as statements from "@lumeo_hq/openbooks-statements";
import * as tax from "@lumeo_hq/openbooks-tax";
import { runDoctor } from "@lumeo_hq/openbooks-doctor";
import { EXIT, main } from "../src/main.js";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../../..");
const venv = join(repo, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.OPENBOOKS_PYTHON ?? (existsSync(venv) ? venv : undefined);
const fake = join(repo, "packages/js/core/test/fake-engine.mjs");

const BANK = "Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,Pay,,5.00,1005.00\n";
const STRIPE = "balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n";
const work = mkdtempSync(join(tmpdir(), "ob-cli-test-"));
const file = (n: string, t: string) => { const p = join(work, n); writeFileSync(p, t); return p; };

function capture() {
  const o: string[] = [], e: string[] = [];
  return { io: { out: (s: string) => o.push(s), err: (s: string) => e.push(s) }, out: () => o.join(""), err: () => e.join("") };
}

afterEach(() => {
  if (process.env.FAKE_MODE) clearEngineCache();
  delete process.env.FAKE_MODE;
});

describe.skipIf(!python)("openbooks CLI with the real engine", () => {
  const base = ["--currency", "INR", "--opening", "1000", "--python", python ?? ""];

  it("exits 0 when everything is released", async () => {
    const c = capture();
    expect(await main(["run", file("a.csv", BANK), ...base], c.io)).toBe(EXIT.ok);
    expect(c.out()).toContain("a.csv: released bank_csv.v1");
  });

  it("runs files without the run subcommand, also for a family", async () => {
    const c = capture();
    expect(await main([file("d.csv", BANK), ...base], c.io)).toBe(EXIT.ok);
    expect(c.out()).toContain("d.csv: released bank_csv.v1");
    const f = capture();
    expect(await main(["gateways", file("e.csv", BANK), ...base], f.io)).toBe(EXIT.refused);
    expect(f.out()).toContain("refused");
  });

  it("still dispatches real subcommands ahead of the default", async () => {
    const c = capture();
    expect(await main(["engine-info", "--python", python ?? ""], c.io)).toBe(EXIT.ok);
    expect(c.out()).toContain("openbooks.v1");
  });

  it("exits 1 when something is refused, and still prints the rest", async () => {
    const c = capture();
    const code = await main(["run", file("b.csv", BANK), file("c.csv", BANK.replace("1005.00", "1005.01")), ...base], c.io);
    expect(code).toBe(EXIT.refused);
    expect(c.out()).toContain("b.csv: released");
    expect(c.out()).toContain("c.csv: refused BALANCE_MISMATCH");
  });

  it("restricts a family command to its own layouts", async () => {
    const c = capture();
    const code = await main(["gateways", "run", file("d.csv", BANK), file("e.csv", STRIPE), ...base], c.io);
    expect(code).toBe(EXIT.refused);
    expect(c.out()).toContain("d.csv: refused UNKNOWN_LAYOUT");
    expect(c.out()).toContain("e.csv: released stripe_balance.v1");
  });

  it("prints machine-readable JSON with --json", async () => {
    const c = capture();
    await main(["run", file("f.csv", BANK), ...base, "--json"], c.io);
    const j = JSON.parse(c.out());
    expect(j[0]).toMatchObject({ file: "f.csv", status: "released" });
    expect(j[0].document.schema_version).toBe("openbooks.v1");
  });

  it("writes each document as <sha256>.json with --out", async () => {
    const dir = join(work, "out");
    await main(["run", file("g.csv", BANK), ...base, "--out", dir], capture().io);
    const names = readdirSync(dir);
    expect(names).toHaveLength(1);
    expect(names[0]).toMatch(/^[0-9a-f]{64}\.json$/);
    expect(JSON.parse(readFileSync(join(dir, names[0]!), "utf8")).status).toBe("ok");
  });

  it("exits 3 with a message when the input does not exist", async () => {
    const c = capture();
    expect(await main(["run", join(work, "missing.csv"), ...base], c.io)).toBe(EXIT.engine);
    expect(c.err()).toContain("missing.csv");
  });

  it("exits 2 for usage errors", async () => {
    expect(await main(["run"], capture().io)).toBe(EXIT.usage);
    expect(await main(["run", file("h.csv", BANK), "--date-order", "ymd", ...base], capture().io)).toBe(EXIT.usage);
    expect(await main(["run", file("i.csv", BANK), "--timeout", "soon", ...base], capture().io)).toBe(EXIT.usage);
    expect(await main([], capture().io)).toBe(EXIT.usage);
  });

  it("--help exits 0", async () => {
    const c = capture();
    expect(await main(["--help"], c.io)).toBe(EXIT.ok);
    expect(c.out()).toContain("statements");
  });
});

describe("openbooks CLI when the engine is unusable", () => {
  it("prints an actionable error for invalid run flags", async () => {
    const c = capture();
    expect(await main(["run", "file.csv", "--timeout", "2147483648"], c.io)).toBe(EXIT.usage);
    expect(c.err()).toContain("--timeout must be");
  });

  it("exits 3 and says what to do when Python is missing", async () => {
    const c = capture();
    expect(await main(["run", file("j.csv", BANK), "--python", "no-such-python-xyz"], c.io)).toBe(EXIT.engine);
    expect(c.err()).toContain("OPENBOOKS_PYTHON");
  });
});

describe.skipIf(!python)("provider wrappers", () => {
  it("list exactly the layouts the engine knows for their family", async () => {
    const { info } = await findEngine({ python: python! });
    // Engine 0.2 names the provider module (openbooks.statements); 0.1 named its distribution (openbooks-statements).
    const owned = (dist: string) => info.known_layouts.filter((l) => l.distribution.replace("openbooks-", "openbooks.") === dist).map((l) => l.id);
    // The PDF/image layout id is produced by the document front end and is not in the core table.
    expect([...statements.LAYOUTS].filter((l) => l !== "bank_statement_pdf.v1").sort()).toEqual(owned("openbooks.statements").sort());
    expect([...statements.LAYOUTS]).toContain("bank_statement_pdf.v1");
    expect([...gateways.LAYOUTS].sort()).toEqual(owned("openbooks.gateways").sort());
    expect([...tax.LAYOUTS].sort()).toEqual(owned("openbooks.tax").sort());
  });

  it("never release a layout outside their list", async () => {
    const r = await tax.runFile(file("k.csv", STRIPE), { python: python!, currency: "USD" });
    expect(r.kind).toBe("refused");
  });
});

describe("doctor wrapper", () => {
  it.skipIf(!python)("returns the Python-side checks plus a Node check", async () => {
    const rep = await runDoctor({ python: python! });
    expect(rep.schema).toBe("openbooks.doctor.v1");
    expect(rep.checks.map((c) => c.id)).toEqual(expect.arrayContaining(["node.version", "core.import", "registry.load"]));
    expect(rep.ok).toBe(rep.summary.fail === 0);
  });

  it("reports a missing Python as a failed check, not an exception", async () => {
    const rep = await runDoctor({ python: "no-such-python-xyz" });
    expect(rep.ok).toBe(false);
    expect(rep.checks.find((c) => c.id === "engine.python_not_found")).toMatchObject({ status: "fail" });
  });

  it("reports a missing engine as a failed check with the install command", async () => {
    process.env.FAKE_MODE = "no_module";
    const rep = await runDoctor({ python: [process.execPath, fake] });
    expect(rep.checks.find((c) => c.id === "engine.engine_not_installed")?.fix).toContain("pip install");
  });
});

describe("install-engine", () => {
  it("fails with exit 3 and a hint when there is no usable Python, without throwing", async () => {
    const c = capture();
    expect(await main(["install-engine", "--python", join(work, "no-such-python")], c.io)).toBe(EXIT.engine);
    expect(c.err()).toContain("no Python interpreter was found");
    expect(c.err()).toContain("python.org");
  });

  it.skipIf(!python)("does nothing when a working engine is already installed", async () => {
    const c = capture();
    expect(await main(["install-engine", "--python", python ?? ""], c.io)).toBe(EXIT.ok);
    expect(c.out()).toContain("already installed");
  });

  it("--version prints the package version", async () => {
    const c = capture();
    expect(await main(["--version"], c.io)).toBe(EXIT.ok);
    expect(c.out().trim()).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it("the postinstall hook never fails the npm install and does nothing in a source checkout", () => {
    const r = spawnSync(process.execPath, [join(here, "../scripts/postinstall.mjs")], { encoding: "utf8" });
    expect(r.status).toBe(0);
    expect(r.stdout).toBe("");
  });
});
