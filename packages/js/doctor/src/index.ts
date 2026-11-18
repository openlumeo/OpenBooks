import { EngineError, findEngine, runProcess, type DiscoverOptions } from "@openbooks/core";

export type DoctorStatus = "pass" | "warn" | "fail" | "skip";

export interface DoctorCheck {
  id: string;
  status: DoctorStatus;
  detail: string;
  fix?: string;
}

export interface DoctorReport {
  schema: "openbooks.doctor.v1";
  ok: boolean;
  summary: Record<DoctorStatus, number>;
  checks: DoctorCheck[];
}

export interface DoctorOptions extends DiscoverOptions {
  /** Also import PyTorch and load the model (slower). */
  deep?: boolean;
  /** Treat warnings as failures. */
  strict?: boolean;
  timeoutMs?: number;
}

const MIN_NODE = 20;

function report(checks: DoctorCheck[], strict: boolean): DoctorReport {
  const summary = { pass: 0, warn: 0, fail: 0, skip: 0 } as Record<DoctorStatus, number>;
  for (const c of checks) summary[c.status]++;
  return { schema: "openbooks.doctor.v1", ok: summary.fail === 0 && !(strict && summary.warn > 0), summary, checks };
}

function nodeCheck(): DoctorCheck {
  const major = Number(process.versions.node.split(".")[0]);
  return major >= MIN_NODE
    ? { id: "node.version", status: "pass", detail: `Node ${process.versions.node}` }
    : { id: "node.version", status: "fail", detail: `Node ${process.versions.node}`, fix: `Open Books needs Node ${MIN_NODE} or newer` };
}

/**
 * Check this machine: Node, a Python with the engine, and everything the Python-side doctor checks. A missing Python or engine
 * is a failed check in the returned report (that is what doctor is for), not an exception. Only a crash of doctor itself throws.
 */
export async function runDoctor(opts: DoctorOptions = {}): Promise<DoctorReport> {
  const checks: DoctorCheck[] = [nodeCheck()];
  let python: string[];
  try {
    python = (await findEngine(opts)).python;
  } catch (e) {
    if (e instanceof EngineError && ["python_not_found", "engine_not_installed", "engine_version"].includes(e.kind)) {
      checks.push({ id: `engine.${e.kind}`, status: "fail", detail: e.message, ...(e.hint ? { fix: e.hint } : {}) });
      return report(checks, opts.strict ?? false);
    }
    throw e;
  }
  const argv = [...python, "-m", "openbooks_core", "doctor", "--json", ...(opts.deep ? ["--deep"] : [])];
  const r = await runProcess(argv, { timeoutMs: opts.timeoutMs ?? 180_000 });
  if (r.code === 2 && /invalid choice/.test(r.stderr)) {
    checks.push({ id: "doctor.installed", status: "fail", detail: "the Python engine is installed but openbooks-doctor is not", fix: "pip install openbooks-doctor" });
    return report(checks, opts.strict ?? false);
  }
  if (r.code !== 0 && r.code !== 1) {
    throw new EngineError("engine_fault", `doctor failed (exit ${r.code ?? r.signal}): ${r.stderr.trim().slice(-500)}`);
  }
  let py: DoctorReport;
  try { py = JSON.parse(r.stdout) as DoctorReport; } catch { throw new EngineError("bad_output", "doctor printed something that is not JSON"); }
  if (py.schema !== "openbooks.doctor.v1") throw new EngineError("bad_output", `unknown doctor report schema ${String(py.schema)}`);
  return report([...checks, ...py.checks], opts.strict ?? false);
}
