import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { engineCommand, findEngine, type DiscoverOptions, type Engine } from "./discover.js";
import { EngineError } from "./errors.js";
import type { OpenBooksDocument, OpenBooksRefusal } from "./generated/openbooks.js";
import { checkAborted, run, validateTimeout } from "./spawn.js";
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
interface Input { path: string; sha: string }

function isMachineLine(value: unknown): value is MachineLine {
  if (typeof value !== "object" || value === null) return false;
  const line = value as Partial<MachineLine>;
  return typeof line.file === "string" && typeof line.output === "string"
    && (line.internal === undefined || typeof line.internal === "boolean")
    && ((line.status === "ok" && line.code === null) || (line.status === "refused" && typeof line.code === "string"));
}

function flags(o: RunOptions): string[] {
  const a: string[] = [];
  if (o.currency) a.push("--currency", o.currency);
  if (o.opening !== undefined) {
    if (typeof o.opening !== "string" || !/^-?\d+(\.\d+)?$/.test(o.opening)) {
      throw new EngineError("input", 'opening must be a plain decimal string like "1000.00"');
    }
    a.push("--opening", o.opening);
  }
  if (o.account) a.push("--account", o.account);
  if (o.allowDerivedOpening) a.push("--allow-derived-opening");
  if (o.dateOrder) a.push("--date-order", o.dateOrder);
  if (o.ocr === false) a.push("--no-ocr");
  if (o.model) a.push("--model");
  return a;
}

async function sha256(path: string, signal?: AbortSignal): Promise<string> {
  const h = createHash("sha256");
  for await (const chunk of createReadStream(path, { signal })) h.update(chunk as Buffer);
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
  checkAborted(opts.signal);
  const runFlags = flags(opts);
  const timeoutMs = opts.runTimeoutMs ?? 120_000;
  validateTimeout(timeoutMs, "runTimeoutMs");
  const batches: Input[][] = [];
  let batch: Input[] = [];
  let hashes = new Set<string>();
  for (const file of files) {
    const path = resolve(file);
    let sha: string;
    try {
      if (!(await stat(path)).isFile()) throw new Error("not a file");
      sha = await sha256(path, opts.signal);
    } catch (cause) {
      checkAborted(opts.signal);
      throw new EngineError("input", `cannot read ${basename(path)}: ${(cause as Error).message}`, undefined, { cause });
    }
    // Each engine invocation writes one file per hash. Read each result before a later input can overwrite it.
    if (hashes.has(sha)) {
      batches.push(batch);
      batch = [];
      hashes = new Set();
    }
    batch.push({ path, sha });
    hashes.add(sha);
  }
  batches.push(batch);
  checkAborted(opts.signal);
  const engine = await discoverForRun(opts);
  checkAborted(opts.signal);
  const deadline = performance.now() + timeoutMs;
  const results: RunResult[] = [];
  for (const inputs of batches) {
    checkAborted(opts.signal);
    const dir = await mkdtemp(resolve(tmpdir(), "openbooks-"));
    try {
      const remaining = Math.ceil(deadline - performance.now());
      if (remaining < 1) throw new EngineError("timeout", `the engine did not finish within ${timeoutMs} ms`);
      results.push(...await runBatch(engine, dir, inputs, runFlags, opts, remaining));
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }
  return results;
}

async function discoverForRun(opts: RunOptions): Promise<Engine> {
  const { signal } = opts;
  if (!signal) return findEngine(opts);
  let onAbort: () => void = () => {};
  const aborted = new Promise<never>((_, reject) => {
    onAbort = () => reject(new EngineError("aborted", "the run was aborted"));
    signal.addEventListener("abort", onAbort, { once: true });
  });
  try {
    // The discovery probe can be shared with other callers, so cancel this wait without stopping the probe.
    return await Promise.race([findEngine(opts), aborted]);
  } finally {
    signal.removeEventListener("abort", onAbort);
  }
}

async function runBatch(
  engine: Engine, dir: string, inputs: Input[], flags: string[], opts: RunOptions, timeoutMs: number,
): Promise<RunResult[]> {
  const argv = [...engineCommand(engine), "run", "--machine", "--out", dir, ...flags, ...inputs.map((input) => input.path)];
  let r;
  try {
    r = await run(argv, { timeoutMs, signal: opts.signal, maxBytes: opts.maxOutputBytes });
  } catch (cause) {
    if (cause instanceof EngineError) throw cause;
    throw new EngineError("engine_fault", `could not start the engine: ${(cause as Error).message}`, undefined, { cause });
  }
  if (r.code !== 0 && r.code !== 1) {
    throw new EngineError("engine_fault", `the engine failed (exit ${r.code ?? r.signal}): ${lastLines(r.stderr) || "no message"}`,
      "run: openbooks doctor");
  }
  const lines: MachineLine[] = [];
  const records = r.stdout.trim().split(/\r?\n/).filter(Boolean);
  for (const [index, raw] of records.entries()) {
    let value: unknown;
    try { value = JSON.parse(raw); } catch { throw new EngineError("bad_output", "the engine printed something that is not JSON lines"); }
    if (index === records.length - 1 && typeof value === "object" && value !== null && "engine" in value) continue;
    if (!isMachineLine(value)) throw new EngineError("bad_output", `invalid engine result on line ${index + 1}`);
    lines.push(value);
  }
  if (lines.length !== inputs.length) {
    throw new EngineError("bad_output", `expected ${inputs.length} results from the engine, got ${lines.length}`);
  }
  if ((r.code === 1) !== lines.some((line) => line.status === "refused")) {
    throw new EngineError("bad_output", "the engine exit code did not match the reported results");
  }

  const results: RunResult[] = [];
  for (const [index, line] of lines.entries()) {
    checkAborted(opts.signal);
    const { path, sha } = inputs[index]!;
    const name = basename(path);
    const target = join(dir, `${sha}.json`);
    if (line.file !== name || resolve(line.output) !== target) {
      throw new EngineError("bad_output", `the engine's output for ${name} does not belong to that input file`);
    }
    let doc: unknown;
    try { doc = JSON.parse(await readFile(target, { encoding: "utf8", signal: opts.signal })); } catch (cause) {
      checkAborted(opts.signal);
      throw new EngineError("bad_output", `could not read the engine's output for ${name}`, undefined, { cause });
    }
    if (line.status === "ok") {
      checkDocument(doc, validateDocument);
      if (doc.file.sha256 !== sha || doc.file.name !== name) {
        throw new EngineError("bad_output", `the released document for ${name} does not match that input file`);
      }
      if (!doc.assertions.every((assertion) => assertion.passed) || !doc.assertions.some((assertion) => assertion.independent)) {
        throw new EngineError("bad_output", `the released document for ${name} has incomplete assertions`);
      }
    } else {
      checkDocument(doc, validateRefusal);
      if (doc.error.file_sha256 !== sha || doc.error.code !== line.code || Boolean(doc.error.internal) !== Boolean(line.internal)) {
        throw new EngineError("bad_output", `the refusal for ${name} does not match the input file or reported result`);
      }
    }
    results.push(toResult(line, doc, sha, opts.accept));
  }
  return results;
}

function checkDocument<T>(doc: unknown, validate: (value: unknown) => asserts value is T): asserts doc is T {
  try {
    validate(doc);
  } catch (cause) {
    throw new EngineError("bad_output", `${(cause as Error).message}. The installed engine and this package may be different versions.`,
      "install matching versions of @lumeo_hq/openbooks-core and the Python package openbooks", { cause });
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
