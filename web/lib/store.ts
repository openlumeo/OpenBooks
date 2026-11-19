// Thread history lives only in this browser (IndexedDB). Results are kept; original file bytes are not.
import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { FileRun, Thread, Turn } from "./types";

interface OpenBooksDB extends DBSchema {
  threads: { key: string; value: Thread; indexes: { byUpdated: number } };
}

const DB_NAME = "openbooks";
let dbp: Promise<IDBPDatabase<OpenBooksDB>> | null = null;

function db() {
  dbp ??= openDB<OpenBooksDB>(DB_NAME, 1, {
    upgrade(d) {
      const s = d.createObjectStore("threads", { keyPath: "id" });
      s.createIndex("byUpdated", "updatedAt");
    },
  });
  return dbp;
}

export async function listThreads(): Promise<Thread[]> {
  const all = await (await db()).getAllFromIndex("threads", "byUpdated");
  return all.reverse().map((thread) => ({
    ...thread,
    turns: thread.turns.map((turn): Turn => {
      if (turn.kind === "run" && (turn.state === "running" || (turn.state === "done" && turn.files.some((file) => !file.doc)))) {
        return {
          ...turn,
          state: "error",
          error: turn.error ?? "The previous session ended before this run finished.",
          files: turn.files.map((file): FileRun => ({ ...file, state: file.doc ? "done" : "interrupted" })),
        };
      }
      if (turn.kind === "answer" && turn.state === "streaming") {
        return { ...turn, state: "error", error: "The previous session ended before this answer finished." };
      }
      return turn;
    }),
  }));
}

export async function getThread(id: string): Promise<Thread | undefined> {
  return (await db()).get("threads", id);
}

export async function saveThread(t: Thread): Promise<void> {
  await (await db()).put("threads", t);
}

export async function deleteThread(id: string): Promise<void> {
  await (await db()).delete("threads", id);
}

export async function clearThreads(): Promise<void> {
  await (await db()).clear("threads");
}

/** Test hook: forget the open connection so a fresh fake IndexedDB can be used. */
export function _resetForTests() {
  dbp = null;
}
