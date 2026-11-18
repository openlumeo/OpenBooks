import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { findEngine, type DiscoverOptions, type Engine } from "./discover.js";
import { EngineError } from "./errors.js";
import type { OpenBooksDocument, OpenBooksRefusal } from "./generated/openbooks.js";
import { run } from "./spawn.js";
import { validateDocument, validateRefusal } from "./validate.js";

export interface RunOptions extends DiscoverOptions {
  currency?: string;
  /** Opening balance as a plain decimal string, e.g. "1000.00". Never a number: money is not floating point. */
  opening?: string;
  account?: string;
  allowDerivedOpening?: boolean;
  dateOrder?: "dmy" | "mdy";
  /** Read scans with OCR (default true). */
  ocr?: boolean;
  /** Cross-check PDFs and scans with the typed model heads. */
  model?: boolean;
  /** Stop the engine after this long (default 120 000 ms). */
  runTimeoutMs?: number;
  signal?: AbortSignal;
  /** Kill the engine if it prints more than this many bytes on stdout or stderr (default 16 MiB). */
  maxOutputBytes?: number;
  /** Only these layout ids may be released; a file that proves out under another layout comes back refused (UNKNOWN_LAYOUT). */
  accept?: readonly string[];
}

export interface Released {
  kind: "released";
  file: string;
  document: OpenBooksDocument;
}

export interface Refused {
  kind: "refused";
  file: string;
  /** REFUSAL code: UNKNOWN_LAYOUT, UNSUPPORTED_INPUT, PARSE_ERROR, BALANCE_MISMATCH, LOW_CONFIDENCE, OUTPUT_INVALID. */
  code: string;
  message: string;
  document: OpenBooksRefusal;
  /** True when the engine refused because of an unexpected internal exception rather than something in the document. */
  internal: boolean;
  /** True when this package withheld a document that proved out, because it is not one of the layouts `accept` allows. */
  restricted: boolean;
}

export type RunResult = Released | Refused;

export const isReleased = (r: RunResult): r is Released => r.kind === "released";

interface MachineLine { file: string; status: "ok" | "refused"; code: string | null; output: string; internal?: boolean }

function flags(o: RunOptions): string[] {
  const a: string[] = [];
  if (o.currency) a.push("--currency", o.currency);
  if (o.opening !== undefined) {
    if (!/^-?\d+(\.\d+)?$/.test(o.opening)) throw new EngineError("input", `opening must be a plain decimal string like "1000.00", got ${JSON.stringify(o.opening)}`);
    a.push("--opening", o.opening);
  }
  if (o.account) a.push("--account", o.account);
  if (o.allowDerivedOpening) a.push("--allow-derived-opening");
  if (o.dateOrder) a.push("--date-order", o.dateOrder);
  if (o.ocr === false) a.push("--no-ocr");
  if (o.model) a.push("--model");
  return a;
}

async function sha256(path: string): Promise<string> {
  const h = createHash("sha256");
  for await (const chunk of createReadStream(path)) h.update(chunk as Buffer);
  return h.digest("hex");
}

function lastLines(s: string, n = 6): string {
  return s.trim().split(/\r?\n/).slice(-n).join("\n").slice(0, 2000);
}

/**
 * Run the engine on one or more files. Every file yields a value: Released, or Refused with its typed code. The promise
 * rejects with EngineError only when the engine itself could not do its job (no Python, no engine, crash, timeout, output
 * that does not match the contract). A refusal is never thrown.
 */
export async function runFiles(files: readonly string[], opts: RunOptions = {}): Promise<RunResult[]> {
  if (files.length === 0) return [];
  const paths = files.map((f) => resolve(f));
  const hashes: string[] = [];
  for (const p of paths) {
    try {
      if (!(await stat(p)).isFile()) throw new Error("not a file");
    } catch {
      throw new EngineError("input", `cannot read ${basename(p)}: it does not exist or is not a file`);
    }
    hashes.push(await sha256(p));
  }
  const engine: Engine = await findEngine(opts);
  const dir = await mkdtemp(join(tmpdir(), "openbooks-"));
  try {
    const argv = [...engine.python, "-m", "openbooks_core", "run", "--machine", "--out", dir, ...flags(opts), ...paths];
    let r;
    try {
      r = await run(argv, { timeoutMs: opts.runTimeoutMs ?? 120_000, signal: opts.signal, maxBytes: opts.maxOutputBytes });
    } catch (e) {
      if (e instanceof EngineError) throw e;
      throw new EngineError("engine_fault", `could not start the engine: ${(e as Error).message}`, undefined, { cause: e });
    }
    if (r.code !== 0 && r.code !== 1) {
      throw new EngineError("engine_fault", `the engine failed (exit ${r.code ?? r.signal}): ${lastLines(r.stderr) || "no message"}`,
        "run: openbooks doctor");
    }
    const lines: MachineLine[] = [];
    for (const raw of r.stdout.split(/\r?\n/).filter(Boolean)) {
      let j: unknown;
      try { j = JSON.parse(raw); } catch { throw new EngineError("bad_output", "the engine printed something that is not JSON lines"); }
      if (typeof j === "object" && j !== null && "status" in j) lines.push(j as MachineLine);
    }
    if (lines.length !== paths.length) {
      throw new EngineError("bad_output", `expected ${paths.length} results from the engine, got ${lines.length}`);
    }
    const results: RunResult[] = [];
    for (const [i, line] of lines.entries()) {
      const expectSha = hashes[i]!;
      if (basename(line.output) !== `${expectSha}.json`) {
        throw new EngineError("bad_output", `the engine's output for ${line.file} does not belong to that input file`);
      }
      let doc: unknown;
      try { doc = JSON.parse(await readFile(line.output, "utf8")); } catch (e) {
        throw new EngineError("bad_output", `could not read the engine's output for ${line.file}`, undefined, { cause: e });
      }
      try {
        if (line.status === "ok") validateDocument(doc);
        else validateRefusal(doc);
      } catch (e) {
        throw new EngineError("bad_output", `${(e as Error).message}. The installed engine and this package may be different versions.`,
          "install matching versions of @lumeo_hq/openbooks-core and openbooks-core", { cause: e });
      }
      results.push(toResult(line, doc as OpenBooksDocument | OpenBooksRefusal, expectSha, opts.accept));
    }
    return results;
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

function toResult(line: MachineLine, doc: OpenBooksDocument | OpenBooksRefusal, sha: string, accept?: readonly string[]): RunResult {
  if (doc.status === "ok") {
    const layout = doc.file.layout_version;
    if (accept && !accept.includes(layout)) {
      const message = `this file is ${layout}, which is not one of the layouts this command reads (${accept.join(", ")})`;
      return {
        kind: "refused", file: line.file, code: "UNKNOWN_LAYOUT", message, internal: false, restricted: true,
        document: { schema_version: "openbooks.v1", status: "refused", data: null, error: { code: "UNKNOWN_LAYOUT", message, file_sha256: sha } },
      };
    }
    return { kind: "released", file: line.file, document: doc };
  }
  return { kind: "refused", file: line.file, code: doc.error.code, message: doc.error.message, document: doc,
           internal: line.internal === true, restricted: false };
}

export async function runFile(file: string, opts: RunOptions = {}): Promise<RunResult> {
  const [r] = await runFiles([file], opts);
  return r!;
}
