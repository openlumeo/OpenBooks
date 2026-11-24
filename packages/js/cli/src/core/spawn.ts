import { spawn, spawnSync } from "node:child_process";
import { EngineError } from "./errors.js";

export interface SpawnResult {
  code: number | null;
  signal: NodeJS.Signals | null;
  stdout: string;
  stderr: string;
}

export interface SpawnOptions {
  timeoutMs: number;
  signal?: AbortSignal;
  maxBytes?: number;
  cwd?: string;
}

export const MAX_TIMEOUT_MS = 2_147_483_647;

export function validateTimeout(timeoutMs: number, option: string): void {
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > MAX_TIMEOUT_MS) {
    throw new EngineError("input", `${option} must be a whole number from 1 to ${MAX_TIMEOUT_MS} milliseconds`);
  }
}

export function checkAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new EngineError("aborted", "the run was aborted");
}

export function killTree(pid: number | undefined): void {
  if (pid === undefined) return;
  try {
    if (process.platform === "win32") {
      const result = spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true, timeout: 5_000 });
      if (result.status !== 0) process.kill(pid, "SIGKILL");
    } else process.kill(-pid, "SIGKILL");
  } catch {
    try { process.kill(pid, "SIGKILL"); } catch { }
  }
}

export async function run(argv: readonly string[], opts: SpawnOptions): Promise<SpawnResult> {
  checkAborted(opts.signal);
  validateTimeout(opts.timeoutMs, "timeoutMs");
  const [cmd, ...args] = argv;
  if (!cmd) return Promise.reject(new Error("empty command"));
  const max = opts.maxBytes ?? 16 * 1024 * 1024;
  if (!Number.isSafeInteger(max) || max < 1) {
    throw new EngineError("input", "maxBytes must be a positive whole number of bytes");
  }
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      shell: false,
      windowsHide: true,
      cwd: opts.cwd,
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
    });
    const out: Buffer[] = [];
    const err: Buffer[] = [];
    const size = { out: 0, err: 0 };
    let ended: EngineError | null = null;
    const end = (e: EngineError) => { if (!ended) { ended = e; killTree(child.pid); } };
    const timer = setTimeout(() => end(new EngineError("timeout", `the engine did not finish within ${opts.timeoutMs} ms and was stopped`)), opts.timeoutMs);
    const onAbort = () => end(new EngineError("aborted", "the run was aborted"));
    opts.signal?.addEventListener("abort", onAbort, { once: true });
    const take = (which: "out" | "err", list: Buffer[]) => (chunk: Buffer) => {
      size[which] += chunk.length;
      if (size[which] > max) end(new EngineError("engine_fault", `the engine produced more than ${max} bytes of output and was stopped`));
      else list.push(chunk);
    };
    child.stdout.on("data", take("out", out));
    child.stderr.on("data", take("err", err));
    child.once("error", (e) => { clearTimeout(timer); opts.signal?.removeEventListener("abort", onAbort); reject(ended ?? e); });
    child.once("close", (code, signal) => {
      clearTimeout(timer);
      opts.signal?.removeEventListener("abort", onAbort);
      if (ended) return reject(ended);
      resolve({ code, signal, stdout: Buffer.concat(out).toString("utf8"), stderr: Buffer.concat(err).toString("utf8") });
    });
  });
}
