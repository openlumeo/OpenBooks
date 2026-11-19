import { readFileSync } from "node:fs";
import { clearEngineCache, EngineError, findEngine, runProcess } from "@lumeo_hq/openbooks-core";

export interface InstallOptions {
  /** Also install OCR and the typed heads (EasyOCR, PyTorch, Pillow). Large. */
  scan?: boolean;
  /** Install into this interpreter instead of searching for one. */
  python?: string;
  /** Reinstall even when a working engine is already present. */
  force?: boolean;
  timeoutMs?: number;
  log?: (line: string) => void;
}

export type InstallResult =
  | { status: "present"; detail: string }
  | { status: "installed"; detail: string }
  | { status: "failed"; detail: string; hint?: string };

/** npm and PyPI share a major.minor line (the contract version); patch releases are independent. So 0.1.x of this CLI takes any openbooks 0.1.x. */
function engineRange(): string {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };
  const [major, minor] = pkg.version.split(".");
  return `~=${major}.${minor}.0`;
}

function pythonCandidates(explicit?: string): string[][] {
  const given = explicit ?? process.env.OPENBOOKS_PYTHON;
  if (given) return [[given]];
  return process.platform === "win32" ? [["py", "-3"], ["python"]] : [["python3"], ["python"]];
}

/** The first interpreter that is Python 3.11 or newer, or why none was. */
async function pickPython(explicit?: string): Promise<{ python: string[] } | { problem: string }> {
  let sawOld = false;
  for (const python of pythonCandidates(explicit)) {
    try {
      const r = await runProcess([...python, "-c", "import sys; print(int(sys.version_info >= (3, 11)))"], { timeoutMs: 15_000 });
      if (r.code !== 0) continue;
      if (r.stdout.trim() === "1") return { python };
      sawOld = true;
    } catch { /* not found or not runnable: try the next one */ }
  }
  return { problem: sawOld ? "Python was found but it is older than 3.11" : "no Python interpreter was found" };
}

/** Install the Python engine (the `openbooks` PyPI package: core, statements with PDF, gateways, tax, doctor) so the JS packages can run. Never throws. */
export async function installEngine(opts: InstallOptions = {}): Promise<InstallResult> {
  const log = opts.log ?? (() => {});
  const range = engineRange();

  if (!opts.force && !opts.scan) { // --scan adds an extra to an existing engine, so it always runs pip (which is a no-op when nothing is missing)
    try {
      const e = await findEngine(opts.python ? { python: opts.python } : {});
      return { status: "present", detail: `the Open Books engine ${e.info.version} is already installed` };
    } catch (e) {
      // A version mismatch is fixed by installing the matching release; anything else means "not there yet".
      if (!(e instanceof EngineError)) return { status: "failed", detail: (e as Error).message };
    }
  }

  const picked = await pickPython(opts.python);
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
    return { status: "installed", detail: `installed the Open Books engine ${e.info.version}` };
  } catch (e) {
    return { status: "failed", detail: `pip succeeded but the engine does not load: ${(e as Error).message}`, hint: "run: openbooks doctor" };
  }
}
