import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, rename, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Command, CommanderError } from "commander";
import { EngineError, findEngine, MAX_TIMEOUT_MS, runFiles, type RunOptions, type RunResult } from "./core/index.js";
import * as gateways from "./gateways/index.js";
import * as statements from "./statements/index.js";
import * as tax from "./tax/index.js";
import { runDoctor } from "./doctor/index.js";
import { installEngine } from "./install-engine.js";
import { formatDoctorText, formatRunJson, formatRunText } from "./output.js";

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
  maxDocumentBytes?: string;
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
    .option("--no-model", "skip the model cross-check for PDFs and scans")
    .option("--out <dir>", "also write each document, named <sha256>.json, into this directory")
    .option("--json", "print the results as JSON instead of one line per file")
    .option("--python <path>", "the Python interpreter that has Open Books installed (default: OPENBOOKS_PYTHON, ./.venv, then the system Python)")
    .option("--timeout <ms>", "stop the engine after this many milliseconds (default 120000)")
    .option("--max-document-bytes <bytes>", "maximum bytes per proof document (default 67108864)");
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
  if (f.model !== undefined) o.model = f.model;
  if (f.python) o.python = f.python;
  if (f.timeout !== undefined) o.runTimeoutMs = parseTimeout(f.timeout);
  if (f.maxDocumentBytes !== undefined) o.maxDocumentBytes = parseMaxDocumentBytes(f.maxDocumentBytes);
  return o;
}

function usageError(message: string): CommanderError {
  return new CommanderError(EXIT.usage, "openbooks.badOption", message);
}

export function parseTimeout(raw: string): number {
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1 || n > MAX_TIMEOUT_MS) {
    throw usageError(`--timeout must be a whole number from 1 to ${MAX_TIMEOUT_MS} milliseconds`);
  }
  return n;
}

export function parseMaxDocumentBytes(raw: string): number {
  const bytes = Number(raw);
  if (!/^[0-9]+$/.test(raw) || !Number.isSafeInteger(bytes) || bytes < 1) {
    throw usageError("--max-document-bytes must be a positive whole number");
  }
  return bytes;
}

async function writeAtomic(path: string, text: string): Promise<void> {
  const tmp = `${path}.${randomUUID()}.tmp`;
  try {
    await writeFile(tmp, text, { encoding: "utf8", flag: "wx" });
    await rename(tmp, path);
  } finally {
    await rm(tmp, { force: true });
  }
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
  io.out(flags.json ? formatRunJson(results) : formatRunText(results));
  return results.every((r) => r.kind === "released") ? EXIT.ok : EXIT.refused;
}

export async function main(argv: string[], io: IO = { out: (s) => process.stdout.write(s), err: (s) => process.stderr.write(s) }): Promise<number> {
  let code: number = EXIT.ok;
  const program = new Command("openbooks")
    .description("Financial documents in, one proven JSON per file out (or a typed refusal). Usage: openbooks <files...> [options]")
    .version((JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string }).version, "-V, --version", "print the version")
    .exitOverride()
    .configureOutput({ writeOut: io.out, writeErr: io.err });
  const set = (n: number) => { code = n; };

  addRunOptions(program.command("run", { isDefault: true }).description("read any supported file").argument("<files...>"))
    .action(async (files: string[], f: RunFlags) => set(await runAndReport(files, f, runFiles, io)));

  const family = (name: string, desc: string, run: Runner) => {
    const g = program.command(name).description(desc);
    addRunOptions(g.command("run", { isDefault: true }).description(`read ${name} files only; anything else is refused`).argument("<files...>"))
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
      io.out(f.json ? JSON.stringify(rep, null, 2) + "\n" : formatDoctorText(rep));
      set(rep.ok ? EXIT.ok : EXIT.refused);
    });

  program.command("install-engine").description("install the Python engine (pip install openbooks) that these packages run on")
    .option("--scan", "also install OCR and the typed heads (EasyOCR, PyTorch: a large download)")
    .option("--force", "reinstall even if a working engine is already present")
    .option("--python <path>", "install into this Python interpreter")
    .action(async (f: { scan?: boolean; force?: boolean; python?: string }) => {
      const r = await installEngine({ ...(f.scan ? { scan: true } : {}), ...(f.force ? { force: true } : {}), ...(f.python ? { python: f.python } : {}), log: (l) => io.out(`${l}\n`) });
      if (r.status === "failed") {
        io.err(`openbooks: ${r.detail}\n${r.hint ? `  ${r.hint}\n` : ""}`);
        set(EXIT.engine);
      } else io.out(`${r.detail}\n`);
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
    if (e instanceof CommanderError) {
      if (e.code === "openbooks.badOption") io.err(`openbooks: ${e.message}\n`);
      return e.exitCode === 0 ? EXIT.ok : EXIT.usage;
    }
    if (e instanceof EngineError) {
      io.err(`openbooks: ${e.message}\n${e.hint ? `  ${e.hint}\n` : ""}`);
      if (/\[scan\]/.test(e.message)) io.err("  or, with the npm package: openbooks install-engine --scan\n");
      return EXIT.engine;
    }
    io.err(`openbooks: unexpected error: ${(e as Error).message}\n`);
    return EXIT.engine;
  }
}
