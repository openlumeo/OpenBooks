import { useCallback, useEffect, useRef, useState } from "react";
import { uid } from "../format";
import * as store from "../store";
import type { Thread, Turn } from "../types";

const SAVE_DEBOUNCE_MS = 400;

/**
 * The thread list and its persistence. Every change goes through commit(), synchronously, so async flows (stream handlers,
 * relink, persistence) always read exactly what will render. React state only mirrors it. Never mutate threads through a
 * setState updater: updaters run lazily and can be replayed, which lets the saved copy drift from the screen.
 */
export function useThreadStore() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [storageError, setStorageError] = useState<string | null>(null);
  const threadsRef = useRef<Thread[]>([]);
  const activeRef = useRef<string | null>(null);
  const saveTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const commit = useCallback((fn: (prev: Thread[]) => Thread[]) => {
    threadsRef.current = fn(threadsRef.current);
    setThreads(threadsRef.current);
  }, []);

  const activate = useCallback((id: string | null) => {
    activeRef.current = id;
    setActiveId(id);
  }, []);

  useEffect(() => {
    let alive = true;
    store.listThreads().then((list) => {
      if (alive) commit(() => list);
    }).catch(() => {
      if (alive) setStorageError("Could not load history from this browser.");
    }).finally(() => {
      if (alive) setLoaded(true);
    });
    return () => { alive = false; };
  }, [commit]);

  /** Write a thread to browser storage, debounced unless `now` is set. Only the latest state is ever written. */
  const persist = useCallback((id: string, now = false) => {
    const timers = saveTimers.current;
    clearTimeout(timers.get(id));
    const write = () => {
      timers.delete(id);
      const thread = threadsRef.current.find((t) => t.id === id);
      if (thread) store.saveThread(thread).catch(() => {
        setStorageError("Could not save a change to browser history. Download any results you need before leaving.");
      });
    };
    if (now) write();
    else timers.set(id, setTimeout(write, SAVE_DEBOUNCE_MS));
  }, []);

  const updateThread = useCallback(
    (id: string, fn: (t: Thread) => Thread, now = false) => {
      commit((prev) => prev.map((t) => (t.id === id ? fn(t) : t)));
      persist(id, now);
    },
    [commit, persist],
  );

  const updateTurn = useCallback(
    <T extends Turn>(threadId: string, turnId: string, fn: (t: T) => T, now = false) => {
      updateThread(threadId, (th) => ({
        ...th,
        updatedAt: Date.now(),
        turns: th.turns.map((t) => (t.id === turnId ? fn(t as T) : t)),
      }), now);
    },
    [updateThread],
  );

  const appendTurns = useCallback(
    (threadId: string, turns: Turn[]) => {
      updateThread(threadId, (th) => ({ ...th, updatedAt: Date.now(), turns: [...th.turns, ...turns] }), true);
    },
    [updateThread],
  );

  /** The active thread's id, or a new thread (made active) when none is selected. */
  const ensureThread = useCallback(
    (title: string): string => {
      const cur = activeRef.current;
      const existing = cur && threadsRef.current.find((t) => t.id === cur);
      if (existing) return existing.id;
      const now = Date.now();
      const thread: Thread = { id: uid(), title, createdAt: now, updatedAt: now, turns: [] };
      commit((prev) => [thread, ...prev]);
      activate(thread.id);
      return thread.id;
    },
    [activate, commit],
  );

  return {
    threads, loaded, activeId, storageError, setStorageError,
    threadsRef, activeRef, saveTimers,
    commit, activate, updateThread, updateTurn, appendTurns, ensureThread,
  };
}
