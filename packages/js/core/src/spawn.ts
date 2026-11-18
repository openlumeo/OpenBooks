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
  /** Output beyond this many bytes (per stream) kills the process: a runaway engine must not exhaust memory. */
  maxBytes?: number;
  cwd?: string;
}

/** Kill a process and its children. Node's own kill() only ends the direct child, which on Windows leaves grandchildren running. */
export function killTree(pid: number | undefined): void {
  if (pid === undefined) return;
  try {
    if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true });
    else process.kill(-pid, "SIGKILL");
  } catch {
    try { process.kill(pid, "SIGKILL"); } catch { /* already gone */ }
  }
}

/** Run argv (no shell) and collect its output. Rejects with ENOENT-style errors untouched so callers can try the next interpreter. */
export function run(argv: readonly string[], opts: SpawnOptions): Promise<SpawnResult> {
  const [cmd, ...args] = argv;
  if (!cmd) return Promise.reject(new Error("empty command"));
  const max = opts.maxBytes ?? 16 * 1024 * 1024;
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      shell: false,
      windowsHide: true,
      cwd: opts.cwd,
      detached: process.platform !== "win32", // own process group on POSIX so the whole tree can be killed
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
    });
    const out: Buffer[] = [];
    const err: Buffer[] = [];
    let size = { out: 0, err: 0 };
    let ended: EngineError | null = null;
    const end = (e: EngineError) => { if (!ended) { ended = e; killTree(child.pid); } };
    const timer = setTimeout(() => end(new EngineError("timeout", `the engine did not finish within ${opts.timeoutMs} ms and was stopped`)), opts.timeoutMs);
    const onAbort = () => end(new EngineError("aborted", "the run was aborted"));
    if (opts.signal?.aborted) onAbort();
    opts.signal?.addEventListener("abort", onAbort, { once: true });
    const take = (which: "out" | "err", list: Buffer[]) => (chunk: Buffer) => {
      size[which] += chunk.length;
      if (size[which] > max) end(new EngineError("engine_fault", `the engine produced more than ${max} bytes of output and was stopped`));
      else list.push(chunk);
    };
    child.stdout.on("data", take("out", out));
    child.stderr.on("data", take("err", err));
    child.once("error", (e) => { clearTimeout(timer); opts.signal?.removeEventListener("abort", onAbort); reject(e); });
    child.once("close", (code, signal) => {
      clearTimeout(timer);
      opts.signal?.removeEventListener("abort", onAbort);
      if (ended) return reject(ended);
      resolve({ code, signal, stdout: Buffer.concat(out).toString("utf8"), stderr: Buffer.concat(err).toString("utf8") });
    });
  });
}
