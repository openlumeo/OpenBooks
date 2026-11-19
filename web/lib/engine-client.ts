// Browser-side calls. Everything goes through this app's own /api routes.
import { parseNDJSON, parseSSE } from "./sse";
import type { EngineDoc, Formats, Health, LinkReport, ReleasedDoc, RolesDoc, RunParams, Sample, Stage } from "./types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function json<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError((body as { message?: string; detail?: string }).message ?? (body as { detail?: string }).detail ?? `HTTP ${res.status}`, res.status);
  return body as T;
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

export type RunEvent =
  | { type: "started"; index: number; name: string; size: number }
  | { type: "stage"; index: number; stage: Stage }
  | { type: "done"; index: number; doc: EngineDoc }
  | { type: "finished"; released: number; refused: number }
  | { type: "error"; message: string };

export async function* runFiles(
  files: File[],
  params: RunParams,
  perFile: Record<number, RunParams>,
  signal?: AbortSignal,
): AsyncGenerator<RunEvent> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  fd.append("params", JSON.stringify(params));
  if (Object.keys(perFile).length) fd.append("file_params", JSON.stringify(perFile));
  const res = await fetch("/api/runs", { method: "POST", body: fd, signal });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    const msg = (body as { detail?: unknown; message?: string }).message ?? (body as { detail?: unknown }).detail;
    throw new ApiError(typeof msg === "string" ? msg : `The engine returned HTTP ${res.status}`, res.status);
  }
  for await (const ev of parseSSE(res.body)) {
    const d = JSON.parse(ev.data);
    switch (ev.event) {
      case "file.started": yield { type: "started", index: d.index, name: d.name, size: d.size }; break;
      case "file.stage": yield { type: "stage", index: d.index, stage: d.stage }; break;
      case "file.done": yield { type: "done", index: d.index, doc: d.doc }; break;
      case "run.done": yield { type: "finished", released: d.released, refused: d.refused }; return;
      case "run.error": throw new Error(d.message || "The engine could not finish this run.");
    }
  }
  throw new Error("The connection ended before the engine confirmed the run.");
}

/** The typed heads' own reading of one PDF or scan: per word role, value type, conformal sets and abstention. */
export async function predictRoles(file: File, params: Pick<RunParams, "ocr" | "date_order"> = {}): Promise<RolesDoc> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  fd.append("params", JSON.stringify(params));
  return json<RolesDoc>(await fetch("/api/roles", { method: "POST", body: fd }));
}

export async function linkDocs(docs: ReleasedDoc[], signal?: AbortSignal): Promise<LinkReport> {
  const res = await fetch("/api/link", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ docs }), signal });
  return json<LinkReport>(res);
}

export type AskEvent =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; summary: string }
  | { type: "error"; message: string }
  | { type: "done" };

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
