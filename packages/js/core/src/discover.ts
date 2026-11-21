import { existsSync } from "node:fs";
import { join } from "node:path";
import { EngineError, INSTALL_HINT } from "./errors.js";
import { run } from "./spawn.js";

/** The contract version and layout API this package was built against. A different engine is refused, not guessed at. */
export const SUPPORTED_SCHEMA_VERSION = "openbooks.v1";
export const SUPPORTED_LAYOUT_API = 1;

export interface EngineInfo {
  name: string;
  version: string;
  schema_version: string;
  layout_api: number;
  python: string;
  layouts: string[];
  known_layouts: { id: string; distribution: string }[];
  frontends: string[];
  linker: boolean;
}

export interface Engine {
  /** The interpreter command, e.g. ["py", "-3"] or ["C:\\...\\python.exe"]. */
  python: string[];
  info: EngineInfo;
  /** The module run with `python -m`: "openbooks" (engine 0.2+) or "openbooks_core" (engine 0.1). Absent means "openbooks". */
  module?: string;
}

/** Engine 0.2 ships everything in the `openbooks` package; 0.1 split it and ran as `openbooks_core`. Both speak the same contract. */
const ENGINE_MODULES = ["openbooks", "openbooks_core"] as const;

/** The argv prefix that runs an engine command: `python -m <module>`. */
export function engineCommand(engine: Engine): string[] {
  return [...engine.python, "-m", engine.module ?? "openbooks"];
}

export interface DiscoverOptions {
  /** An interpreter to use instead of searching: a path, or a command with its leading arguments. */
  python?: string | readonly string[];
  timeoutMs?: number;
}

const cache = new Map<string, Promise<Engine>>();
const CACHE_LIMIT = 64;

function candidates(opts: DiscoverOptions): string[][] {
  const explicit = opts.python ?? process.env.OPENBOOKS_PYTHON;
  if (explicit) return [typeof explicit === "string" ? [explicit] : [...explicit]];
  const win = process.platform === "win32";
  const venv = win ? join(process.cwd(), ".venv", "Scripts", "python.exe") : join(process.cwd(), ".venv", "bin", "python");
  return [...(existsSync(venv) ? [[venv]] : []), ...(win ? [["py", "-3"], ["python"]] : [["python3"], ["python"]])];
}

function isNotFound(e: unknown): boolean {
  return typeof e === "object" && e !== null && (e as NodeJS.ErrnoException).code === "ENOENT";
}

function isEngineInfo(value: unknown): value is EngineInfo {
  if (!value || typeof value !== "object") return false;
  const info = value as Partial<EngineInfo>;
  return typeof info.name === "string" && typeof info.version === "string"
    && typeof info.schema_version === "string" && typeof info.layout_api === "number"
    && typeof info.python === "string" && typeof info.linker === "boolean"
    && Array.isArray(info.layouts) && info.layouts.every((x) => typeof x === "string")
    && Array.isArray(info.frontends) && info.frontends.every((x) => typeof x === "string")
    && Array.isArray(info.known_layouts) && info.known_layouts.every(
      (x) => x && typeof x.id === "string" && typeof x.distribution === "string",
    );
}

async function probe(python: string[], timeoutMs: number): Promise<Engine | "no_engine" | "not_python"> {
  for (const module of ENGINE_MODULES) {
    let r;
    try {
      r = await run([...python, "-m", module, "engine-info"], { timeoutMs });
    } catch (e) {
      if (isNotFound(e)) return "not_python";
      throw e;
    }
    // "No module named openbooks" (nothing installed) or "No module named openbooks.__main__" (engine 0.1): try the next name.
    if (r.code !== 0) {
      if (/No module named ['"]?openbooks/.test(r.stderr)) continue;
      return "not_python";
    }
    const invalid = () => new EngineError("bad_output", "the Python engine returned invalid engine-info");
    let info: unknown;
    try { info = JSON.parse(r.stdout); } catch { throw invalid(); }
    if (!isEngineInfo(info)) throw invalid();
    return { python, info, module };
  }
  return "no_engine";
}

/** Find a Python that has the Open Books engine, and check it speaks the contract this package understands. */
export function findEngine(opts: DiscoverOptions = {}): Promise<Engine> {
  const key = JSON.stringify([opts.python ?? null, process.env.OPENBOOKS_PYTHON ?? null, process.cwd(), opts.timeoutMs ?? 30_000]);
  let p = cache.get(key);
  if (!p) {
    p = discover(opts);
    const discovery = p;
    p.catch(() => { if (cache.get(key) === discovery) cache.delete(key); });
    cache.set(key, p);
    if (cache.size > CACHE_LIMIT) {
      const oldest = cache.keys().next().value;
      if (oldest !== undefined) cache.delete(oldest);
    }
  }
  return p;
}

export function clearEngineCache(): void { cache.clear(); }

async function discover(opts: DiscoverOptions): Promise<Engine> {
  const timeoutMs = opts.timeoutMs ?? 30_000;
  let sawPython = false;
  for (const python of candidates(opts)) {
    const r = await probe(python, timeoutMs);
    if (r === "not_python") continue;
    sawPython = true;
    if (r === "no_engine") continue;
    if (r.info.schema_version !== SUPPORTED_SCHEMA_VERSION || r.info.layout_api !== SUPPORTED_LAYOUT_API) {
      throw new EngineError("engine_version",
        `the installed engine (openbooks ${r.info.version}) speaks ${r.info.schema_version}, layout API ${r.info.layout_api}; ` +
        `this package needs ${SUPPORTED_SCHEMA_VERSION}, layout API ${SUPPORTED_LAYOUT_API}`,
        "install matching versions of @lumeo_hq/openbooks-core and the Python package openbooks");
    }
    return r;
  }
  if (!sawPython) {
    throw new EngineError("python_not_found", "no Python interpreter was found (tried the .venv in the working directory, then the system Python)",
      "install Python 3.11 or newer, or set OPENBOOKS_PYTHON to an interpreter that has Open Books installed");
  }
  throw new EngineError("engine_not_installed", "Python was found, but the Open Books engine is not installed in it", INSTALL_HINT);
}
