import { fileKeys } from "../query";
import type { EngineDoc, Thread } from "../types";

export const HISTORY_MESSAGES = 12;
const TITLE_MAX_CHARS = 60;
const TITLE_KEEP_CHARS = 57;

export type ChatMessage = { role: "user" | "assistant"; content: string };

export function titleFor(files: File[], text: string): string {
  if (files.length) return files.length === 1 ? files[0]!.name : `${files[0]!.name} + ${files.length - 1} more`;
  const collapsed = text.trim().replace(/\s+/g, " ");
  return collapsed.length > TITLE_MAX_CHARS ? `${collapsed.slice(0, TITLE_KEEP_CHARS)}…` : collapsed || "Untitled run";
}

export function threadDocs(thread: Thread | undefined): { file: string; doc: EngineDoc }[] {
  if (!thread) return [];
  const runs = thread.turns.flatMap((t) => (t.kind === "run" ? t.files.filter((f) => f.doc) : []));
  const keys = fileKeys(runs.map((f) => f.name));
  return runs.map((f, i) => ({ file: keys[i]!, doc: f.doc! }));
}

export function priorExchanges(thread: Thread | undefined): ChatMessage[] {
  const history: ChatMessage[] = [];
  let previousQuestion: string | undefined;
  for (const turn of thread?.turns ?? []) {
    if (turn.kind === "user-ask") previousQuestion = turn.text;
    if (turn.kind !== "answer") continue;
    if (previousQuestion && turn.state === "done" && !turn.error && turn.text.trim()) {
      history.push({ role: "user", content: previousQuestion }, { role: "assistant", content: turn.text });
    }
    previousQuestion = undefined;
  }
  return history;
}

export function trimHistory(history: ChatMessage[]): ChatMessage[] {
  let out = history.slice(-HISTORY_MESSAGES);
  while (out.length && out[0]!.role !== "user") out = out.slice(1);
  return out;
}
