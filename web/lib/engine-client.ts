import { parseNDJSON, parseSSE } from "./sse";
import type { EngineDoc, Formats, Health, LinkReport, ReleasedDoc, RolesDoc, RunParams, Sample, Stage } from "./types";

class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function json<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError((body as { message?: string; detail?: string }).message ?? (body as { detail?: string }).detail ?? `HTTP ${res.status}`, res.status);
  return body as T;
}

type JobEvent = { event: string; data: unknown };
type JobPage = { events: JobEvent[]; cursor: number; done: boolean };
const JOB_HEADER = "x-openbooks-job";
const POLL_MS = 2000;
const JOB_TIMEOUT_MS = 30 * 60 * 1000;
const DIRECT_UPLOAD_BYTES = 4 * 1024 * 1024;

function jobHeaders(): Record<string, string> {
  const key = Array.from(crypto.getRandomValues(new Uint8Array(16)), (n) => n.toString(16).padStart(2, "0")).join("");
  return { [JOB_HEADER]: key };
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  signal?.throwIfAborted();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve();
    }, ms);
    function abort() {
      clearTimeout(timer);
      reject(signal?.reason);
    }
    signal?.addEventListener("abort", abort, { once: true });
  });
}

async function* pollJob(path: string, headers: Record<string, string>, signal?: AbortSignal): AsyncGenerator<JobEvent> {
  const deadline = Date.now() + JOB_TIMEOUT_MS;
  let cursor = 0;
  let retries = 0;
  let delay = POLL_MS;
  while (Date.now() < deadline) {
    await wait(delay, signal);
    const res = await fetch(`${path}?cursor=${cursor}`, { headers, signal, cache: "no-store" }).catch((error: unknown) => {
      if (signal?.aborted) throw error;
      return undefined;
    });
    if ((!res || [429, 502, 503, 504].includes(res.status)) && retries < 5) {
      await res?.body?.cancel().catch(() => undefined);
      retries += 1;
      delay = Math.max(POLL_MS * retries, (Number(res?.headers.get("retry-after")) || 0) * 1000);
      continue;
    }
    if (!res) throw new Error("Could not reconnect to the engine. Try again.");
    const page = await json<JobPage>(res);
    retries = 0;
    cursor = page.cursor;
    for (const event of page.events) yield event;
    if (page.done) return;
    delay = page.events.length ? POLL_MS : Math.min(6000, delay + 1000);
  }
  throw new Error("The engine is still processing this file. Try again with a shorter document.");
}

function jobError(data: unknown): Error {
  const message = (data as { message?: string })?.message;
  return new Error(message || "The engine could not finish this job.");
}

export const getHealth = () => fetch("/api/engine/health", { cache: "no-store" }).then((r) => json<Health>(r));
export const getFormats = () => fetch("/api/engine/formats").then((r) => json<Formats>(r));
export const getSamples = () => fetch("/api/engine/samples").then((r) => json<{ samples: Sample[] }>(r)).then((b) => b.samples);
export const getAskStatus = () => fetch("/api/ask", { cache: "no-store" }).then((r) => json<{ enabled: boolean }>(r));

export async function fetchSampleFile(s: Sample, signal?: AbortSignal): Promise<File> {
  const res = await fetch(`/api/engine/samples/${encodeURIComponent(s.id)}`, { signal });
  if (!res.ok) throw new ApiError(`Could not load sample ${s.filename}`, res.status);
  return new File([await res.blob()], s.filename, { type: "application/octet-stream" });
}

type RunEvent =
  | { type: "started"; index: number; name: string; size: number }
  | { type: "stage"; index: number; stage: Stage }
  | { type: "done"; index: number; doc: EngineDoc }
  | { type: "finished"; released: number; refused: number }
  | { type: "error"; message: string };

async function uploadTarget(path: string, bytes: number, headers: Record<string, string>, signal?: AbortSignal, retain = false) {
  const production = typeof window !== "undefined" && window.location.origin === "https://books.openlumeo.com";
  if (retain && !production) throw new Error("Saving originals is available only on the live workspace.");
  if (!production || (!retain && bytes < DIRECT_UPLOAD_BYTES)) {
    return { url: path, headers };
  }
  const tokenHeaders = retain ? { ...headers, "x-openbooks-retain": "1" } : headers;
  const token = await fetch("/api/upload-token", { method: "POST", headers: tokenHeaders, signal }).then((res) => json<{ token: string }>(res));
  return { url: `https://uploads.books.openlumeo.com${path}`, headers: { ...headers, authorization: `Bearer ${token.token}` } };
}

export async function* runFiles(
  files: File[],
  params: RunParams,
  perFile: Record<number, RunParams>,
  signal?: AbortSignal,
  retain = false,
): AsyncGenerator<RunEvent> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  fd.append("params", JSON.stringify(params));
  if (Object.keys(perFile).length) fd.append("file_params", JSON.stringify(perFile));
  const { url, headers } = await uploadTarget("/api/runs", files.reduce((total, file) => total + file.size, 0), jobHeaders(), signal, retain);
  const res = await fetch(url, { method: "POST", body: fd, headers, signal });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    const msg = (body as { detail?: unknown; message?: string }).message ?? (body as { detail?: unknown }).detail;
    throw new ApiError(typeof msg === "string" ? msg : `The engine returned HTTP ${res.status}`, res.status);
  }
  const events = res.status === 202 ? pollJob(url, headers, signal) : (async function* () {
    for await (const event of parseSSE(res.body!)) yield { event: event.event, data: JSON.parse(event.data) };
  })();
  if (res.status === 202) await res.body.cancel().catch(() => undefined);
  for await (const ev of events) {
    const d = ev.data as { index: number; name: string; size: number; stage: Stage; doc: EngineDoc; released: number; refused: number };
    switch (ev.event) {
      case "file.started": yield { type: "started", index: d.index, name: d.name, size: d.size }; break;
      case "file.stage": yield { type: "stage", index: d.index, stage: d.stage }; break;
      case "file.done": yield { type: "done", index: d.index, doc: d.doc }; break;
      case "run.done": yield { type: "finished", released: d.released, refused: d.refused }; return;
      case "run.error":
      case "error": throw jobError(ev.data);
    }
  }
  throw new Error("The connection ended before the engine confirmed the run.");
}

export async function predictRoles(file: File, params: RunParams = {}, signal?: AbortSignal): Promise<RolesDoc> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  fd.append("params", JSON.stringify(params));
  const { url, headers } = await uploadTarget("/api/roles", file.size, jobHeaders(), signal);
  const res = await fetch(url, { method: "POST", body: fd, headers, signal });
  if (res.status !== 202) return json<RolesDoc>(res);
  await res.body?.cancel().catch(() => undefined);
  for await (const event of pollJob(url, headers, signal)) {
    if (event.event === "roles") return event.data as RolesDoc;
    if (event.event === "error") throw jobError(event.data);
  }
  throw new Error("The engine finished without returning a model reading.");
}

export async function linkDocs(docs: ReleasedDoc[], signal?: AbortSignal): Promise<LinkReport> {
  const res = await fetch("/api/link", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ docs }), signal });
  return json<LinkReport>(res);
}

type AskEvent =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; summary: string }
  | { type: "error"; message: string }
  | { type: "done"; usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number; reported_turns: number; turns: number } };

export async function* ask(
  body: { question: string; history: { role: "user" | "assistant"; content: string }[]; docs: { file: string; doc: EngineDoc }[] },
  signal?: AbortSignal,
): AsyncGenerator<AskEvent> {
  const res = await fetch("/api/ask", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal });
  if (!res.ok || !res.body) {
    const b = await res.json().catch(() => ({}));
    throw new ApiError((b as { message?: string }).message ?? `HTTP ${res.status}`, res.status);
  }
  for await (const event of parseNDJSON<AskEvent>(res.body)) {
    if (event.type === "error") throw new Error(event.message);
    yield event;
    if (event.type === "done") return;
  }
  throw new Error("The connection ended before the answer completed.");
}
