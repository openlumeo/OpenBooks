import type { Thread } from "./types";

const files = new Map<string, File[]>();

export function rememberFiles(turnId: string, list: File[]) {
  files.set(turnId, list);
}

export function recallFile(turnId: string, index: number): File | undefined {
  return files.get(turnId)?.[index];
}

export function forgetThreadFiles(thread: Thread) {
  for (const turn of thread.turns) {
    if (turn.kind === "user-run") files.delete(turn.id);
  }
}

export function clearSessionFiles() {
  files.clear();
}
