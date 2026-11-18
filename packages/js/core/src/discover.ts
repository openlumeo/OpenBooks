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
}

export interface DiscoverOptions {
  /** An interpreter to use instead of searching: a path, or a command with its leading arguments. */
  python?: string | readonly string[];
  timeoutMs?: number;
}

const cache = new Map<string, Promise<Engine>>();

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

async function probe(python: string[], timeoutMs: number): Promise<Engine | "no_engine" | "not_python"> {
  let r;
  try {
    r = await run([...python, "-m", "openbooks_core", "engine-info"], { timeoutMs });
  } catch (e) {
    if (isNotFound(e)) return "not_python";
    throw e;
  }
  if (r.code !== 0) return /No module named ['"]?openbooks_core/.test(r.stderr) ? "no_engine" : "not_python";
  let info: EngineInfo;
  try { info = JSON.parse(r.stdout) as EngineInfo; } catch { return "not_python"; }
  return { python, info };
}

/** Find a Python that has the Open Books engine, and check it speaks the contract this package understands. */
export function findEngine(opts: DiscoverOptions = {}): Promise<Engine> {
  const key = JSON.stringify([opts.python ?? null, process.env.OPENBOOKS_PYTHON ?? null, process.cwd()]);
  let p = cache.get(key);
  if (!p) {
    p = discover(opts);
    p.catch(() => cache.delete(key)); // never cache a failure: the user may install the engine and retry
    cache.set(key, p);
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
        `the installed engine (openbooks-core ${r.info.version}) speaks ${r.info.schema_version}, layout API ${r.info.layout_api}; ` +
        `this package needs ${SUPPORTED_SCHEMA_VERSION}, layout API ${SUPPORTED_LAYOUT_API}`,
        "install matching versions of @lumeo_hq/openbooks-core and openbooks-core");
    }
    return r;
  }
  if (!sawPython) {
    throw new EngineError("python_not_found", "no Python interpreter was found (tried the .venv in the working directory, then the system Python)",
      "install Python 3.11 or newer, or set OPENBOOKS_PYTHON to an interpreter that has Open Books installed");
  }
  throw new EngineError("engine_not_installed", "Python was found, but the Open Books engine is not installed in it", INSTALL_HINT);
}
