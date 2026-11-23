import { mkdtemp, realpath, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { extname, isAbsolute, join, parse, relative, sep } from "node:path";
import { EngineError, findEngine, runFile, type DocumentOptions, type DiscoverOptions, type RunResult } from "@lumeo_hq/openbooks-core";
import { z } from "zod";
import {
  COLLECTIONS,
  DOCUMENT_STATUSES,
  EXTENSIONS,
  MAX_CONCURRENT_RUNS,
  MAX_DOCUMENT_BYTES,
  MAX_ENCODED_UPLOAD,
  MAX_RECORD_PAGE,
  MAX_REF_BYTES,
  MAX_REF_DEPTH,
  MAX_REFUSAL_MESSAGE,
  MAX_RESPONSE_BYTES,
  MAX_STEPS,
  MAX_UPLOAD_BYTES,
  MAX_VERIFY_MANY,
  PROMPT_NAMES,
  REFUSAL_CODES,
  RESOURCE_URIS,
  SAMPLE_STATEMENT,
  STEP_ENVELOPE_BYTES,
  TOOL_NAMES,
} from "./constants.js";
import { WORKSPACE_PACKAGES } from "./workspace.generated.js";

export type Doc = Record<string, unknown>;
type Documents = Map<string, Doc>;

const INSTALL_FIX = "Run: npx -y @lumeo_hq/openbooks install-engine --scan";
const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;
const FORBIDDEN_KEYS: ReadonlySet<string> = new Set(["__proto__", "constructor", "prototype"]);

const stepId = z.string().regex(/^[A-Za-z][A-Za-z0-9_-]{0,31}$/);
const opening = z.string().max(32).regex(/^[+-]?[0-9]+(\.[0-9]+)?$/);

export const StepSchema = z.object({
  id: stepId,
  operation: z.string().max(40),
  arguments: z.record(z.string(), z.unknown()).default({}),
}).strict();
export type StepInput = z.input<typeof StepSchema>;

const processing = {
  currency: z.string().regex(/^[A-Z]{3}$/).optional(),
  opening: opening.optional(),
  date_order: z.enum(["dmy", "mdy"]).optional(),
  account: z.string().max(128).optional(),
  allow_derived_opening: z.boolean().default(false),
  ocr: z.boolean().default(true),
  model: z.boolean().default(false),
};

const NoArguments = z.object({}).strict();
const SampleInput = z.object({ opening: opening.optional() }).strict();
const FileInput = z.object({ ...processing, path: z.string().min(1).max(512) }).strict();
const UploadInput = z.object({
  ...processing,
  filename: z.string().regex(/^[a-zA-Z0-9][a-zA-Z0-9._ -]{0,127}$/),
  content_base64: z.string().min(4).max(MAX_ENCODED_UPLOAD),
}).strict();
const DetailsInput = z.object({ details: z.boolean().default(false) }).strict();
const UploadItem = z.object({
  filename: UploadInput.shape.filename,
  content_base64: UploadInput.shape.content_base64,
}).strict();
const VerifyManyInput = z.object({
  ...processing,
  files: z.array(z.string().min(1).max(512)).max(MAX_VERIFY_MANY).default([]),
  uploads: z.array(UploadItem).max(MAX_VERIFY_MANY).default([]),
}).strict().refine((args) => args.files.length + args.uploads.length >= 1 && args.files.length + args.uploads.length <= MAX_VERIFY_MANY, {
  message: `Supply between 1 and ${MAX_VERIFY_MANY} files and uploads in total.`,
});
const DocumentInput = z.object({ from_step: stepId }).strict();
const RecordsInput = z.object({
  from_step: stepId,
  collection: z.enum(COLLECTIONS),
  offset: z.number().int().min(0).max(1_000_000).default(0),
  limit: z.number().int().min(1).max(MAX_RECORD_PAGE).default(5),
  prefix: z.string().max(80).default(""),
}).strict();

type ProcessingArguments = z.infer<z.ZodObject<typeof processing>>;

export class OperationError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
  }
}

interface Operation {
  description: string;
  schema: z.ZodType;
  run: (raw: unknown, documents: Documents, step: string) => Promise<Doc>;
}

function define<S extends z.ZodType>(description: string, schema: S, run: (args: z.infer<S>, documents: Documents, step: string) => Promise<Doc>): Operation {
  return { description, schema, run: (raw, documents, step) => run(schema.parse(raw), documents, step) };
}

function errorItem(id: string, code: string, message: string): Doc {
  return { id, error: { code, message } };
}

function documentOptions(args: ProcessingArguments): DocumentOptions {
  const options: DocumentOptions = { allowDerivedOpening: args.allow_derived_opening, ocr: args.ocr, model: args.model };
  if (args.currency !== undefined) options.currency = args.currency;
  if (args.opening !== undefined) options.opening = args.opening;
  if (args.date_order !== undefined) options.dateOrder = args.date_order;
  if (args.account !== undefined) options.account = args.account;
  return options;
}

async function withTempFile<T>(payload: Buffer, filename: string, use: (path: string) => Promise<T>): Promise<T> {
  const directory = await mkdtemp(join(tmpdir(), "openbooks-mcp-"));
  try {
    const path = join(directory, filename);
    await writeFile(path, payload);
    return await use(path);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

function summarise(result: RunResult, documents: Documents, step: string): Doc {
  const document = result.document as unknown as Doc;
  documents.set(step, document);
  const summary = { schema_version: document.schema_version, status: document.status };
  if (result.kind === "refused") {
    return { ...summary, error: { code: result.code, message: result.message.slice(0, MAX_REFUSAL_MESSAGE) } };
  }
  const data = (document.data ?? {}) as Record<string, unknown>;
  const assertions = Array.isArray(document.assertions) ? document.assertions.length : 0;
  return {
    ...summary,
    file: document.file,
    counts: Object.fromEntries(Object.entries(data).map(([name, items]) => [name, Array.isArray(items) ? items.length : 0])),
    assertions,
  };
}

function stripNulls(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stripNulls);
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(Object.entries(value).filter(([, entry]) => entry !== null).map(([key, entry]) => [key, stripNulls(entry)]));
}

function byteLength(value: unknown): number {
  return Buffer.byteLength(JSON.stringify(value));
}

function isRef(value: unknown): value is { $ref: string } {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const keys = Object.keys(value);
  return keys.length === 1 && keys[0] === "$ref" && typeof (value as Doc).$ref === "string";
}

function lookup(roots: ReadonlyMap<string, unknown>, reference: string): unknown {
  const [id, ...path] = reference.split(".");
  if (id === undefined || !roots.has(id)) throw new OperationError("BAD_REF", "A $ref must start with the id of an earlier successful step.");
  if (path.length > MAX_REF_DEPTH) throw new OperationError("BAD_REF", "The $ref path is too deep.");
  let current: unknown = roots.get(id);
  for (const segment of path) {
    const isIndex = Array.isArray(current) && /^[0-9]+$/.test(segment);
    const readable = typeof current === "object" && current !== null && !FORBIDDEN_KEYS.has(segment) && Object.hasOwn(current, segment);
    if (!isIndex && !readable) throw new OperationError("BAD_REF", `The $ref path does not exist at "${segment.slice(0, 40)}".`);
    current = (current as Record<string, unknown>)[segment];
    if (current === undefined) throw new OperationError("BAD_REF", `The $ref path does not exist at "${segment.slice(0, 40)}".`);
  }
  if (byteLength(current) > MAX_REF_BYTES) throw new OperationError("BAD_REF", "The referenced value is too large to substitute.");
  return current;
}

function resolveRefs(value: unknown, roots: ReadonlyMap<string, unknown>, depth = 0): unknown {
  if (depth > MAX_REF_DEPTH) throw new OperationError("BAD_REF", "Arguments are nested too deeply.");
  if (isRef(value)) return lookup(roots, value.$ref);
  if (Array.isArray(value)) return value.map((item) => resolveRefs(item, roots, depth + 1));
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolveRefs(item, roots, depth + 1)]));
  }
  return value;
}

function dependsOnEarlierStep(value: unknown): boolean {
  if (isRef(value)) return true;
  if (Array.isArray(value)) return value.some(dependsOnEarlierStep);
  if (typeof value !== "object" || value === null) return false;
  return Object.entries(value).some(([key, item]) => key === "from_step" || dependsOnEarlierStep(item));
}

async function inBatches<T>(items: readonly T[], size: number, run: (item: T) => Promise<Doc>): Promise<Doc[]> {
  const out: Doc[] = [];
  for (let start = 0; start < items.length; start += size) {
    out.push(...(await Promise.all(items.slice(start, start + size).map(run))));
  }
  return out;
}

function storedDocument(documents: Documents, from: string): Doc {
  const document = documents.get(from);
  if (!document) throw new OperationError("MISSING_DOCUMENT", "Reference an earlier processing step in this batch.");
  return document;
}

export interface OperationsOptions {
  root?: string;
  engine?: DiscoverOptions;
}

export interface ExecuteOptions {
  parallel?: boolean;
  stop_on_error?: boolean;
}

export interface ExecuteResult {
  steps?: Doc[];
  error?: { code: string; message: string };
}

export class Operations {
  private readonly root: string | undefined;
  private readonly engine: DiscoverOptions;
  private readonly operations = new Map<string, Operation>();
  private active = 0;

  constructor(options: OperationsOptions = {}) {
    this.root = options.root;
    this.engine = options.engine ?? {};
    this.operations.set("doctor", define("Check the install: engine version, limits, available formats and a live proof that a known statement verifies.", NoArguments, (_args, _documents, _step) => this.doctor()));
    this.operations.set("formats", define("List installed layouts and file limits for CSV, PDF, scans and financial exports.", NoArguments, () => this.formats()));
    this.operations.set("process_sample", define("Verify a synthetic bank statement CSV. Supply opening 1000.00 for a release.", SampleInput, (args, documents, step) => this.processSample(args, documents, step)));
    this.operations.set("process_upload", define("Verify a file sent as base64 bytes, up to 1 MiB.", UploadInput, (args, documents, step) => this.processUpload(args, documents, step)));
    this.operations.set("records", define("Read a bounded page of transactions, batches, accounts, claims, assertions or evidence from an earlier step.", RecordsInput, (args, documents, step) => this.records(args, documents, step)));
    this.operations.set("document", define("Return the complete released or refused JSON from an earlier step, subject to the response limit.", DocumentInput, (args, documents) => Promise.resolve(storedDocument(documents, args.from_step))));
    this.operations.set("verify_many", define("Verify up to 8 files and uploads in one step and return a compact status per file.", VerifyManyInput, (args, _documents, step) => this.verifyMany(args, step)));
    this.operations.set("packages", define("List the npm packages in this workspace with version and role, plus the Python engine version. Pass details true for the full list.", DetailsInput, (args) => this.packages(args.details)));
    this.operations.set("capabilities", define("Count and list supported layouts, input formats, extensions, refusal codes, operations, tools, resources and prompts. Pass details true for the lists.", DetailsInput, (args) => this.capabilities(args.details)));
    if (this.root !== undefined) {
      this.operations.set("process_file", define("Verify a file at a relative path inside the user-approved local folder.", FileInput, (args, documents, step) => this.processFile(args, documents, step)));
    }
  }

  search(query: string, details: boolean): { operations: Doc[]; max_steps: number } {
    const terms = new Set(query.toLowerCase().match(/[a-z0-9]+/g) ?? []);
    const matches: { score: number; item: Doc }[] = [];
    for (const [name, operation] of this.operations) {
      const keywords = new Set(`${name} ${operation.description}`.toLowerCase().match(/[a-z0-9]+/g) ?? []);
      const score = [...terms].filter((term) => keywords.has(term)).length;
      if (terms.size > 0 && score === 0) continue;
      const item: Doc = { name, description: operation.description };
      if (details) item.arguments = z.toJSONSchema(operation.schema);
      matches.push({ score, item });
    }
    matches.sort((a, b) => b.score - a.score);
    return { operations: matches.map((match) => match.item), max_steps: MAX_STEPS };
  }

  async execute(steps: readonly StepInput[], options: ExecuteOptions = {}): Promise<ExecuteResult> {
    if (new Set(steps.map((step) => step.id)).size !== steps.length) {
      return { error: { code: "DUPLICATE_STEP", message: "Step ids must be unique." } };
    }
    const parallel = options.parallel ?? false;
    const stopOnError = options.stop_on_error ?? true;
    if (parallel && steps.some((step) => dependsOnEarlierStep(step.arguments))) {
      return { error: { code: "PARALLEL_DEPENDENCY", message: "Parallel steps cannot use from_step or $ref. Run dependent steps in order." } };
    }
    if (this.active >= MAX_CONCURRENT_RUNS) {
      return { error: { code: "BUSY", message: "Retry after outstanding runs finish." } };
    }
    this.active += 1;
    const documents: Documents = new Map();
    const outputs = new Map<string, unknown>();
    const results: Doc[] = [];
    try {
      const budget = MAX_RESPONSE_BYTES - MAX_STEPS * STEP_ENVELOPE_BYTES;
      const size = parallel ? MAX_CONCURRENT_RUNS : 1;
      let halted = false;
      for (let start = 0; start < steps.length; start += size) {
        const chunk = steps.slice(start, start + size);
        const items = halted
          ? chunk.map((step) => errorItem(step.id, "SKIPPED", "An earlier step failed and stop_on_error is true."))
          : await Promise.all(chunk.map((step) => this.runStep(step, documents, outputs)));
        for (const item of items) {
          results.push(byteLength([...results, item]) > budget ? errorItem(String(item.id), "RESPONSE_LIMIT", "Request fewer records or a smaller page.") : item);
        }
        if (stopOnError && items.some((item) => "error" in item)) halted = true;
      }
      return { steps: results };
    } finally {
      this.active -= 1;
    }
  }

  private async runStep(step: StepInput, documents: Documents, outputs: Map<string, unknown>): Promise<Doc> {
    try {
      const operation = this.operations.get(step.operation);
      if (!operation) throw new OperationError("UNKNOWN_OPERATION", "Use search to find available operations.");
      const roots = new Map<string, unknown>([...outputs, ...documents]);
      const args = resolveRefs(step.arguments ?? {}, roots);
      const result = stripNulls(await operation.run(args, documents, step.id)) as Doc;
      outputs.set(step.id, result);
      return { id: step.id, result };
    } catch (error) {
      if (error instanceof z.ZodError) return errorItem(step.id, "INVALID_ARGUMENTS", "Check the operation's argument schema with search.");
      if (error instanceof OperationError) return errorItem(step.id, error.code, error.message);
      if (error instanceof EngineError) return errorItem(step.id, "ENGINE_ERROR", `The engine could not complete this operation. ${INSTALL_FIX}`);
      return errorItem(step.id, "ENGINE_ERROR", "The engine could not complete this operation. Check the install and input.");
    }
  }

  private async engineInfo() {
    try {
      return await findEngine(this.engine);
    } catch (error) {
      if (error instanceof EngineError) return undefined;
      throw error;
    }
  }

  private async selfTest(): Promise<Doc> {
    try {
      const outcome = await withTempFile(Buffer.from(SAMPLE_STATEMENT), "statement.csv", (path) =>
        runFile(path, { ...this.engine, currency: "INR", dateOrder: "dmy", opening: "1000.00" }));
      return { status: outcome.kind === "released" ? "ok" : "refused", released: outcome.kind === "released" };
    } catch (error) {
      return { status: "failed", released: false, reason: error instanceof Error ? error.name : "Error" };
    }
  }

  private limits(): Doc {
    return { max_file_bytes: MAX_DOCUMENT_BYTES, max_upload_bytes: MAX_UPLOAD_BYTES, max_steps: MAX_STEPS, max_response_bytes: MAX_RESPONSE_BYTES };
  }

  private async doctor(): Promise<Doc> {
    const engine = await this.engineInfo();
    if (!engine) {
      return {
        healthy: false,
        engine: { available: false },
        local_files_enabled: this.root !== undefined,
        limits: this.limits(),
        self_test: { status: "skipped", released: false },
        fix: INSTALL_FIX,
      };
    }
    const selfTest = await this.selfTest();
    return {
      healthy: selfTest.released === true,
      engine: { available: true, version: engine.info.version, schema_version: engine.info.schema_version },
      document_frontend: engine.info.frontends.includes("document"),
      layouts: engine.info.layouts,
      local_files_enabled: this.root !== undefined,
      limits: this.limits(),
      self_test: selfTest,
    };
  }

  private async formats(): Promise<Doc> {
    const engine = await this.engineInfo();
    if (!engine) throw new OperationError("ENGINE_UNAVAILABLE", `The Open Books engine is not installed. ${INSTALL_FIX}`);
    return {
      name: engine.info.name,
      version: engine.info.version,
      schema_version: engine.info.schema_version,
      layouts: engine.info.layouts,
      known_layouts: engine.info.known_layouts,
      extensions: [...EXTENSIONS],
      max_file_bytes: MAX_DOCUMENT_BYTES,
      max_upload_bytes: MAX_UPLOAD_BYTES,
    };
  }

  private async processPath(path: string, args: ProcessingArguments, documents: Documents, step: string): Promise<Doc> {
    const result = await runFile(path, { ...this.engine, ...documentOptions(args), maxDocumentBytes: MAX_DOCUMENT_BYTES });
    return summarise(result, documents, step);
  }

  private async processSample(args: z.infer<typeof SampleInput>, documents: Documents, step: string): Promise<Doc> {
    const options: ProcessingArguments = { currency: "INR", date_order: "dmy", allow_derived_opening: false, ocr: true, model: false };
    if (args.opening !== undefined) options.opening = args.opening;
    return withTempFile(Buffer.from(SAMPLE_STATEMENT), "statement.csv", (path) => this.processPath(path, options, documents, step));
  }

  private async processUpload(args: z.infer<typeof UploadInput>, documents: Documents, step: string): Promise<Doc> {
    if (!BASE64.test(args.content_base64) || args.content_base64.length % 4 !== 0) {
      throw new OperationError("INVALID_ENCODING", "Supply standard base64 without a data URL prefix.");
    }
    const payload = Buffer.from(args.content_base64, "base64");
    if (payload.length > MAX_UPLOAD_BYTES) throw new OperationError("INPUT_LIMIT", "The decoded file exceeds 1 MiB.");
    if (!(EXTENSIONS as readonly string[]).includes(extname(args.filename).toLowerCase())) {
      throw new OperationError("UNSUPPORTED_INPUT", "Use an extension listed by the formats operation.");
    }
    return withTempFile(payload, args.filename, (path) => this.processPath(path, args, documents, step));
  }

  private async processFile(args: z.infer<typeof FileInput>, documents: Documents, step: string): Promise<Doc> {
    const root = this.root;
    const parts = args.path.split(/[\\/]+/);
    if (root === undefined || isAbsolute(args.path) || parse(args.path).root !== "" || parts.includes("..") || args.path.includes("\0")) {
      throw new OperationError("INVALID_PATH", "Use a relative path within the approved folder.");
    }
    let resolved: string;
    try {
      resolved = await realpath(join(root, args.path));
      const inside = relative(root, resolved);
      const details = await stat(resolved);
      if (inside === "" || inside === ".." || inside.startsWith(`..${sep}`) || isAbsolute(inside) || !details.isFile()) {
        throw new OperationError("INVALID_PATH", "Use a regular file within the approved folder.");
      }
      if (!(EXTENSIONS as readonly string[]).includes(extname(resolved).toLowerCase())) {
        throw new OperationError("UNSUPPORTED_INPUT", "Use an extension listed by the formats operation.");
      }
      if (details.size > MAX_DOCUMENT_BYTES) throw new OperationError("INPUT_LIMIT", "The local file exceeds the engine limit.");
    } catch (error) {
      if (error instanceof OperationError) throw error;
      throw new OperationError("INVALID_PATH", "The file path could not be resolved.");
    }
    return this.processPath(resolved, args, documents, step);
  }

  private async verifyMany(args: z.infer<typeof VerifyManyInput>, step: string): Promise<Doc> {
    const { files, uploads, ...common } = args;
    const jobs = [
      ...files.map((path) => ({ name: path, run: () => this.processFile({ ...common, path }, new Map(), step) })),
      ...uploads.map((upload) => ({ name: upload.filename, run: () => this.processUpload({ ...common, ...upload }, new Map(), step) })),
    ];
    const results = await inBatches(jobs, MAX_CONCURRENT_RUNS, async (job) => {
      try {
        const summary = await job.run();
        const failure = summary.error as { code?: string } | undefined;
        const counts = summary.counts as Record<string, number> | undefined;
        return stripNulls({ name: job.name, status: summary.status, code: failure?.code, rows: counts?.transactions, assertions: summary.assertions }) as Doc;
      } catch (error) {
        const code = error instanceof OperationError ? error.code : "ENGINE_ERROR";
        return { name: job.name, status: "error", code };
      }
    });
    const tally = (status: string): number => results.filter((result) => result.status === status).length;
    return { total: results.length, ok: tally("ok"), refused: tally("refused"), error: tally("error"), files: results };
  }

  private async packages(details: boolean): Promise<Doc> {
    const engine = await this.engineInfo();
    const summary: Doc = { count: WORKSPACE_PACKAGES.length, engine_available: engine !== undefined };
    if (!details) return summary;
    return {
      ...summary,
      packages: WORKSPACE_PACKAGES.map((entry) => ({ ...entry })),
      engine: engine
        ? { name: engine.info.name, version: engine.info.version, schema_version: engine.info.schema_version, layout_api: engine.info.layout_api, python: engine.info.python, linker: engine.info.linker, frontends: engine.info.frontends }
        : { available: false },
    };
  }

  private async capabilities(details: boolean): Promise<Doc> {
    const engine = await this.engineInfo();
    const counts = {
      operations: this.operations.size,
      tools: TOOL_NAMES.length,
      resources: RESOURCE_URIS.length,
      prompts: PROMPT_NAMES.length,
      extensions: EXTENSIONS.length,
      refusal_codes: Object.keys(REFUSAL_CODES).length,
      collections: COLLECTIONS.length,
      statuses: DOCUMENT_STATUSES.length,
      layouts: engine?.info.layouts.length ?? 0,
      known_layouts: engine?.info.known_layouts.length ?? 0,
      frontends: engine?.info.frontends.length ?? 0,
    };
    const summary: Doc = { engine_available: engine !== undefined, ...counts };
    if (!details) return summary;
    return {
      ...summary,
      operation_names: [...this.operations.keys()],
      tool_names: [...TOOL_NAMES],
      resource_uris: [...RESOURCE_URIS],
      prompt_names: [...PROMPT_NAMES],
      extension_list: [...EXTENSIONS],
      refusal_code_list: Object.keys(REFUSAL_CODES),
      collection_list: [...COLLECTIONS],
      status_list: [...DOCUMENT_STATUSES],
      layout_ids: engine?.info.layouts ?? [],
      known_layout_list: engine?.info.known_layouts ?? [],
      frontend_list: engine?.info.frontends ?? [],
    };
  }

  private async records(args: z.infer<typeof RecordsInput>, documents: Documents, step: string): Promise<Doc> {
    void step;
    const document = storedDocument(documents, args.from_step);
    if (document.status !== "ok") throw new OperationError("DOCUMENT_REFUSED", "Inspect the refusal before requesting records.");
    let records: Doc[];
    if (args.collection === "evidence") {
      const evidence = (document.evidence ?? {}) as Record<string, Doc>;
      records = Object.entries(evidence).filter(([key]) => key.startsWith(args.prefix)).map(([key, value]) => ({ key, ...value }));
    } else {
      const source = args.collection === "assertions" ? document.assertions : (document.data as Record<string, unknown>)[args.collection];
      records = (Array.isArray(source) ? (source as Doc[]) : []).filter((record) => String(record.id ?? "").startsWith(args.prefix));
    }
    const end = args.offset + args.limit;
    return {
      collection: args.collection,
      items: records.slice(args.offset, end),
      total: records.length,
      next_offset: end < records.length ? end : null,
    };
  }
}
