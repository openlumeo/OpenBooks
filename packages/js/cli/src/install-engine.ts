import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { clearEngineCache, EngineError, findEngine, runProcess } from "./core/index.js";

export interface InstallOptions {
  scan?: boolean;
  python?: string;
  force?: boolean;
  timeoutMs?: number;
  log?: (line: string) => void;
}

export type InstallResult =
  | { status: "present"; detail: string }
  | { status: "installed"; detail: string }
  | { status: "failed"; detail: string; hint?: string };

export function engineRange(): string {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };
  const [major, minor] = pkg.version.split(".");
  return `~=${major}.${minor}.0`;
}

function pythonCandidates(explicit?: string): string[][] {
  const given = explicit ?? process.env.OPENBOOKS_PYTHON;
  if (given) return [[given]];
  const win = process.platform === "win32";
  const venv = win ? join(process.cwd(), ".venv", "Scripts", "python.exe") : join(process.cwd(), ".venv", "bin", "python");
  return [...(existsSync(venv) ? [[venv]] : []), ...(win ? [["python"], ["py", "-3"]] : [["python3"], ["python"]])];
}

async function pickPython(explicit?: string): Promise<{ python: string[] } | { problem: string }> {
  let sawOld = false;
  for (const python of pythonCandidates(explicit)) {
    try {
      const r = await runProcess([...python, "-c", "import sys; print(int(sys.version_info >= (3, 11)))"], { timeoutMs: 15_000 });
      if (r.code !== 0) continue;
      if (r.stdout.trim() === "1") return { python };
      sawOld = true;
    } catch { }
  }
  return { problem: sawOld ? "Python was found but it is older than 3.11" : "no Python interpreter was found" };
}

export async function installEngine(opts: InstallOptions = {}): Promise<InstallResult> {
  const log = opts.log ?? (() => {});
  const range = engineRange();
  const versionPrefix = range.slice(2, -1);
  let existingPython: string[] | undefined;

  if (!opts.force && !opts.scan) {
    try {
      const e = await findEngine(opts.python ? { python: opts.python } : {});
      if (e.info.version.startsWith(versionPrefix)) {
        return { status: "present", detail: `the Open Books engine ${e.info.version} is already installed` };
      }
      existingPython = e.python;
    } catch (e) {
      if (!(e instanceof EngineError)) return { status: "failed", detail: (e as Error).message };
    }
  }

  const picked = existingPython ? { python: existingPython } : await pickPython(opts.python);
  if ("problem" in picked) {
    return { status: "failed", detail: picked.problem, hint: "install Python 3.11 or newer from https://www.python.org/downloads/, then run: openbooks install-engine" };
  }

  const spec = `openbooks${opts.scan ? "[scan]" : ""}${range}`;
  log(`installing the Python engine: pip install ${spec}`);
  let r;
  try {
    r = await runProcess([...picked.python, "-m", "pip", "install", "--disable-pip-version-check", spec], { timeoutMs: opts.timeoutMs ?? 15 * 60_000 });
  } catch (e) {
    return { status: "failed", detail: `pip did not finish: ${(e as Error).message}`, hint: `run it yourself: pip install ${spec}` };
  }
  if (r.code !== 0) {
    const tail = r.stderr.trim().split(/\r?\n/).slice(-6).join("\n");
    if (/externally-managed-environment/.test(r.stderr)) {
      return {
        status: "failed",
        detail: "this Python is managed by your operating system and refuses global installs",
        hint: `create a virtual environment and point at it: python3 -m venv .venv && .venv/bin/pip install ${spec}  (Open Books uses ./.venv automatically), or set OPENBOOKS_PYTHON`,
      };
    }
    return { status: "failed", detail: `pip exited with code ${r.code}\n${tail}`, hint: `run it yourself: pip install ${spec}` };
  }

  clearEngineCache();
  try {
    const e = await findEngine({ python: picked.python });
    if (!e.info.version.startsWith(versionPrefix)) {
      return { status: "failed", detail: `pip succeeded but Python still loads Open Books ${e.info.version}`, hint: `install ${spec} in a fresh virtual environment` };
    }
    return { status: "installed", detail: `installed the Open Books engine ${e.info.version}` };
  } catch (e) {
    return { status: "failed", detail: `pip succeeded but the engine does not load: ${(e as Error).message}`, hint: "run: openbooks doctor" };
  }
}
