import { EngineError, engineCommand, findEngine, runProcess, type DiscoverOptions } from "@lumeo_hq/openbooks-core";

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
const DOCTOR_STATUSES = new Set<string>(["pass", "warn", "fail", "skip"]);

function isCheck(value: unknown): value is DoctorCheck {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<DoctorCheck>;
  return typeof item.id === "string" && typeof item.detail === "string"
    && typeof item.status === "string" && DOCTOR_STATUSES.has(item.status)
    && (item.fix === undefined || typeof item.fix === "string");
}

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
  let command: string[];
  try {
    command = engineCommand(await findEngine(opts));
  } catch (e) {
    if (e instanceof EngineError && ["python_not_found", "engine_not_installed", "engine_version"].includes(e.kind)) {
      checks.push({ id: `engine.${e.kind}`, status: "fail", detail: e.message, ...(e.hint ? { fix: e.hint } : {}) });
      return report(checks, opts.strict ?? false);
    }
    throw e;
  }
  const argv = [...command, "doctor", "--json", ...(opts.deep ? ["--deep"] : [])];
  const r = await runProcess(argv, { timeoutMs: opts.timeoutMs ?? 180_000 });
  if (r.code === 2 && /invalid choice/.test(r.stderr)) {
    checks.push({ id: "doctor.installed", status: "fail", detail: "the Python engine is installed but its doctor command is not", fix: "pip install --force-reinstall openbooks" });
    return report(checks, opts.strict ?? false);
  }
  if (r.code !== 0 && r.code !== 1) {
    throw new EngineError("engine_fault", `doctor failed (exit ${r.code ?? r.signal}): ${r.stderr.trim().slice(-500)}`);
  }
  let parsed: unknown;
  try { parsed = JSON.parse(r.stdout); } catch { throw new EngineError("bad_output", "doctor printed something that is not JSON"); }
  const py = parsed as Partial<DoctorReport> | null;
  if (py?.schema !== "openbooks.doctor.v1" || !Array.isArray(py.checks) || !py.checks.every(isCheck)) {
    throw new EngineError("bad_output", "the Python engine returned an invalid doctor report");
  }
  return report([...checks, ...py.checks], opts.strict ?? false);
}
