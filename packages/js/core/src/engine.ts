import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { lstat, mkdtemp, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { engineCommand, findEngine, type DiscoverOptions, type Engine } from "./discover.js";
import { EngineError } from "./errors.js";
import type { OpenBooksDocument, OpenBooksRefusal } from "./generated/openbooks.js";
import { checkAborted, run, validateTimeout } from "./spawn.js";
import { validateDocument, validateRefusal } from "./validate.js";

export interface DocumentOptions {
  currency?: string;
  /** Opening balance as a plain decimal string, e.g. "1000.00". Never a number: money is not floating point. */
  opening?: string;
  account?: string;
  allowDerivedOpening?: boolean;
  dateOrder?: "dmy" | "mdy";
  /** Read scans with OCR (default true). */
  ocr?: boolean;
  /** Cross-check PDFs and scans with the typed model heads (default true). */
  model?: boolean;
}

export interface RunOptions extends DiscoverOptions, DocumentOptions {
  /** Stop the engine after this long (default 120 000 ms). */
  runTimeoutMs?: number;
  signal?: AbortSignal;
  /** Kill the engine if it prints more than this many bytes on stdout or stderr (default 16 MiB). */
  maxOutputBytes?: number;
  /** Maximum serialized bytes for one proof document (default 64 MiB). */
  maxDocumentBytes?: number;
  /** Only these layout ids may be released; a file that proves out under another layout comes back refused (UNKNOWN_LAYOUT). */
  accept?: readonly string[];
}

export interface RunJob {
  file: string;
  options?: DocumentOptions;
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
export interface Input { path: string; sha: string }
const DEFAULT_RUN_TIMEOUT_MS = 120_000;
const DEFAULT_DOCUMENT_BYTES = 64 * 1024 * 1024;
const MAX_ERROR_TAIL_LINES = 6;
const MAX_ERROR_TAIL_CHARS = 2000;
const DOCUMENT_OPTIONS = ["currency", "opening", "account", "allowDerivedOpening", "dateOrder", "ocr", "model"] as const;

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
  if (o.model !== false) a.push("--model");
  return a;
}

async function sha256(path: string, signal?: AbortSignal): Promise<string> {
  const h = createHash("sha256");
  for await (const chunk of createReadStream(path, { signal })) h.update(chunk as Buffer);
  return h.digest("hex");
}

function lastLines(s: string): string {
  return s.trim().split(/\r?\n/).slice(-MAX_ERROR_TAIL_LINES).join("\n").slice(0, MAX_ERROR_TAIL_CHARS);
}

async function hashInput(path: string, signal?: AbortSignal): Promise<string> {
  try {
    if (!(await stat(path)).isFile()) throw new Error("not a file");
    return await sha256(path, signal);
  } catch (cause) {
    checkAborted(signal);
    throw new EngineError("input", `cannot read ${basename(path)}: ${(cause as Error).message}`, undefined, { cause });
  }
}

async function readInputs(files: readonly string[], signal?: AbortSignal): Promise<Input[]> {
  const inputs: Input[] = [];
  for (const file of files) {
    const path = resolve(file);
    inputs.push({ path, sha: await hashInput(path, signal) });
  }
  return inputs;
}

/**
 * Each engine invocation writes one file per content hash, so a repeated input starts a new batch. Results of a batch are
 * read before a later input can overwrite them.
 */
export function splitBatches(inputs: readonly Input[]): Input[][] {
  const batches: Input[][] = [[]];
  let hashes = new Set<string>();
  for (const input of inputs) {
    if (hashes.has(input.sha)) {
      batches.push([]);
      hashes = new Set();
    }
    batches[batches.length - 1]!.push(input);
    hashes.add(input.sha);
  }
  return batches;
}

/** Parse the engine's JSON lines. The engine may end with a non-result trailer that carries its version, which is skipped. */
export function parseMachineLines(stdout: string): MachineLine[] {
  const records = stdout.trim().split(/\r?\n/).filter(Boolean);
  const lines: MachineLine[] = [];
  for (const [index, raw] of records.entries()) {
    let value: unknown;
    try { value = JSON.parse(raw); } catch { throw new EngineError("bad_output", "the engine printed something that is not JSON lines"); }
    if (index === records.length - 1 && typeof value === "object" && value !== null && "engine" in value) continue;
    if (!isMachineLine(value)) throw new EngineError("bad_output", `invalid engine result on line ${index + 1}`);
    lines.push(value);
  }
  return lines;
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
  const timeoutMs = opts.runTimeoutMs ?? DEFAULT_RUN_TIMEOUT_MS;
  validateTimeout(timeoutMs, "runTimeoutMs");
  const maxDocument = opts.maxDocumentBytes ?? DEFAULT_DOCUMENT_BYTES;
  if (!Number.isSafeInteger(maxDocument) || maxDocument < 1) {
    throw new EngineError("input", "maxDocumentBytes must be a positive whole number of bytes");
  }
  const batches = splitBatches(await readInputs(files, opts.signal));
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
      results.push(...await runBatch(engine, dir, inputs, runFlags, opts, remaining, maxDocument));
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }
  return results;
}

/** Process a mixed batch in order, yielding each decision as it finishes. Job overrides are document options only. */
export async function* runJobs(jobs: Iterable<RunJob> | AsyncIterable<RunJob>, opts: RunOptions = {}): AsyncGenerator<RunResult> {
  for await (const job of jobs) {
    checkAborted(opts.signal);
    const overrides = Object.fromEntries(DOCUMENT_OPTIONS.flatMap((key) => {
      const value = job.options?.[key];
      return value === undefined ? [] : [[key, value]];
    }));
    yield await runFile(job.file, { ...opts, ...overrides });
  }
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
  engine: Engine, dir: string, inputs: Input[], flags: string[], opts: RunOptions, timeoutMs: number, maxDocument: number,
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
  const lines = parseMachineLines(r.stdout);
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
    try { doc = await readDocument(target, maxDocument, opts.signal); } catch (cause) {
      checkAborted(opts.signal);
      if (cause instanceof EngineError) throw cause;
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

async function readDocument(path: string, limit: number, signal?: AbortSignal): Promise<unknown> {
  const metadata = await lstat(path);
  const invalid = () => new EngineError("bad_output", `expected a regular proof document no larger than ${limit} bytes`);
  if (!metadata.isFile() || metadata.size > limit) throw invalid();

  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of createReadStream(path, { signal })) {
    size += chunk.length;
    if (size > limit) throw invalid();
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks, size).toString("utf8"));
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
