import { mkdir, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Command, CommanderError } from "commander";
import { EngineError, findEngine, runFiles, type RunOptions, type RunResult } from "@openbooks/core";
import * as gateways from "@openbooks/gateways";
import * as statements from "@openbooks/statements";
import * as tax from "@openbooks/tax";
import { runDoctor } from "@openbooks/doctor";

/** Exit codes match the Python CLI: 0 all released, 1 something was refused, 2 usage, 3 the engine could not run. */
export const EXIT = { ok: 0, refused: 1, usage: 2, engine: 3 } as const;

export interface IO {
  out: (s: string) => void;
  err: (s: string) => void;
}

interface RunFlags {
  currency?: string;
  opening?: string;
  account?: string;
  allowDerivedOpening?: boolean;
  dateOrder?: "dmy" | "mdy";
  ocr?: boolean;
  model?: boolean;
  out?: string;
  json?: boolean;
  python?: string;
  timeout?: string;
}

type Runner = (files: readonly string[], opts: RunOptions) => Promise<RunResult[]>;

function addRunOptions(c: Command): Command {
  return c
    .option("--currency <code>", "currency, if the file does not state one")
    .option("--opening <amount>", "opening balance as a plain decimal such as 1000.00, if the file does not state one")
    .option("--account <number>")
    .option("--allow-derived-opening", "derive the opening balance from the first row (not independent evidence)")
    .option("--date-order <order>", "day/month order of numeric dates: dmy or mdy")
    .option("--no-ocr", "refuse scans instead of running OCR")
    .option("--model", "cross-check PDFs and scans with the typed model heads")
    .option("--out <dir>", "also write each document, named <sha256>.json, into this directory")
    .option("--json", "print the results as JSON instead of one line per file")
    .option("--python <path>", "the Python interpreter that has Open Books installed (default: OPENBOOKS_PYTHON, ./.venv, then the system Python)")
    .option("--timeout <ms>", "stop the engine after this many milliseconds (default 120000)");
}

function toOptions(f: RunFlags): RunOptions {
  if (f.dateOrder && f.dateOrder !== "dmy" && f.dateOrder !== "mdy") throw new CommanderError(2, "openbooks.badOption", "--date-order must be dmy or mdy");
  const o: RunOptions = {};
  if (f.currency) o.currency = f.currency;
  if (f.opening !== undefined) o.opening = f.opening;
  if (f.account) o.account = f.account;
  if (f.allowDerivedOpening) o.allowDerivedOpening = true;
  if (f.dateOrder) o.dateOrder = f.dateOrder;
  if (f.ocr === false) o.ocr = false;
  if (f.model) o.model = true;
  if (f.python) o.python = f.python;
  if (f.timeout !== undefined) {
    const n = Number(f.timeout);
    if (!Number.isInteger(n) || n <= 0) throw new CommanderError(2, "openbooks.badOption", "--timeout must be a positive whole number of milliseconds");
    o.runTimeoutMs = n;
  }
  return o;
}

async function writeAtomic(path: string, text: string): Promise<void> {
  const tmp = `${path}.${process.pid}.tmp`;
  await writeFile(tmp, text, "utf8");
  await rename(tmp, path);
}

async function runAndReport(files: string[], flags: RunFlags, runner: Runner, io: IO): Promise<number> {
  const results = await runner(files, toOptions(flags));
  if (flags.out) {
    await mkdir(flags.out, { recursive: true });
    for (const r of results) {
      const sha = r.kind === "released" ? r.document.file.sha256 : r.document.error.file_sha256;
      await writeAtomic(join(flags.out, `${sha}.json`), JSON.stringify(r.document, null, 2) + "\n");
    }
  }
  if (flags.json) {
    io.out(JSON.stringify(results.map((r) => ({ file: r.file, status: r.kind, ...(r.kind === "refused" ? { code: r.code, message: r.message } : {}), document: r.document })), null, 2) + "\n");
  } else {
    for (const r of results) {
      io.out(r.kind === "released" ? `${r.file}: released ${r.document.file.layout_version}\n` : `${r.file}: refused ${r.code}: ${r.message}\n`);
    }
  }
  return results.every((r) => r.kind === "released") ? EXIT.ok : EXIT.refused;
}

export async function main(argv: string[], io: IO = { out: (s) => process.stdout.write(s), err: (s) => process.stderr.write(s) }): Promise<number> {
  let code: number = EXIT.ok;
  const program = new Command("openbooks")
    .description("Financial documents in, one proven JSON per file out (or a typed refusal). Needs the Python engine: pip install openbooks")
    .exitOverride()
    .configureOutput({ writeOut: io.out, writeErr: io.err });
  const set = (n: number) => { code = n; };

  addRunOptions(program.command("run").description("read any supported file").argument("<files...>"))
    .action(async (files: string[], f: RunFlags) => set(await runAndReport(files, f, runFiles, io)));

  const family = (name: string, desc: string, run: Runner) => {
    const g = program.command(name).description(desc);
    addRunOptions(g.command("run").description(`read ${name} files only; anything else is refused`).argument("<files...>"))
      .action(async (files: string[], f: RunFlags) => set(await runAndReport(files, f, run, io)));
  };
  family("statements", "bank statements: CSV, OFX, MT940, PDF and scans", statements.runFiles);
  family("gateways", "payment gateways: Stripe, Razorpay, PayPal, Wise", gateways.runFiles);
  family("tax", "tax and ledger documents: 26AS, AIS, FIRA, 1099-B, trial balance", tax.runFiles);

  program.command("doctor").description("check this machine: Node, Python, the engine, providers and model integrity")
    .option("--json", "machine-readable output").option("--strict", "treat warnings as failures").option("--deep", "also import PyTorch and load the model")
    .option("--python <path>", "the Python interpreter to check")
    .action(async (f: { json?: boolean; strict?: boolean; deep?: boolean; python?: string }) => {
      const rep = await runDoctor({ deep: f.deep, strict: f.strict, ...(f.python ? { python: f.python } : {}) });
      if (f.json) io.out(JSON.stringify(rep, null, 2) + "\n");
      else {
        for (const c of rep.checks) io.out(`[${c.status.padEnd(4)}] ${c.id}: ${c.detail}\n${c.fix && (c.status === "fail" || c.status === "warn") ? `       fix: ${c.fix}\n` : ""}`);
        io.out(`${rep.summary.pass} passed, ${rep.summary.warn} warnings, ${rep.summary.fail} failed, ${rep.summary.skip} skipped -> ${rep.ok ? "OK" : "NOT OK"}\n`);
      }
      set(rep.ok ? EXIT.ok : EXIT.refused);
    });

  program.command("engine-info").description("print the engine version, contract version and installed layouts as JSON")
    .option("--python <path>", "the Python interpreter to ask")
    .action(async (f: { python?: string }) => {
      io.out(JSON.stringify((await findEngine(f.python ? { python: f.python } : {})).info, null, 2) + "\n");
    });

  try {
    await program.parseAsync(argv, { from: "user" });
    return code;
  } catch (e) {
    if (e instanceof CommanderError) return e.exitCode === 0 ? EXIT.ok : EXIT.usage;
    if (e instanceof EngineError) {
      io.err(`openbooks: ${e.message}\n${e.hint ? `  ${e.hint}\n` : ""}`);
      return EXIT.engine;
    }
    io.err(`openbooks: unexpected error: ${(e as Error).message}\n`);
    return EXIT.engine;
  }
}
