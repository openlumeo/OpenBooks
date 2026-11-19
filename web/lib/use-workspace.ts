"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ask, getAskStatus, getFormats, getHealth, getSamples, linkDocs, runFiles } from "./engine-client";
import { paramSummary, uid } from "./format";
import { fileKeys } from "./query";
import { clearSessionFiles, forgetThreadFiles, recallFile, rememberFiles } from "./session-files";
import * as store from "./store";
import {
  isReleased,
  type AnswerTurn,
  type EngineDoc,
  type FileRun,
  type Formats,
  type Health,
  type LinksTurn,
  type RunParams,
  type RunTurn,
  type Sample,
  type Thread,
  type Turn,
  type UserAskTurn,
  type UserRunTurn,
} from "./types";

export type EngineState = { status: "checking" | "up" | "down"; health?: Health; message?: string };

const HISTORY_MESSAGES = 12;

function titleFor(files: File[], text: string): string {
  if (files.length) return files.length === 1 ? files[0]!.name : `${files[0]!.name} + ${files.length - 1} more`;
  const t = text.trim().replace(/\s+/g, " ");
  return t.length > 60 ? `${t.slice(0, 57)}…` : t || "Untitled run";
}

/** Every file result in the thread, in order, with a unique key the Q&A model can address. */
export function threadDocs(thread: Thread | undefined): { file: string; doc: EngineDoc }[] {
  if (!thread) return [];
  const runs = thread.turns.flatMap((t) => (t.kind === "run" ? t.files.filter((f) => f.doc) : []));
  const keys = fileKeys(runs.map((f) => f.name));
  return runs.map((f, i) => ({ file: keys[i]!, doc: f.doc! }));
}

export function useWorkspace() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [engine, setEngine] = useState<EngineState>({ status: "checking" });
  const [formats, setFormats] = useState<Formats | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [askEnabled, setAskEnabled] = useState<boolean | null>(null);
  const [operation, setOperation] = useState<"run" | "link" | "ask" | "history" | null>(null);
  const [storageError, setStorageError] = useState<string | null>(null);

  // Single source of truth. Every change goes through commit(), synchronously, so async flows
  // (stream handlers, relink, persistence) always read exactly what will render. React state
  // only mirrors it. Never mutate threads through a setState updater: updaters run lazily and
  // can be replayed, which let the saved copy drift from the screen.
  const threadsRef = useRef<Thread[]>([]);
  const commit = useCallback((fn: (prev: Thread[]) => Thread[]) => {
    threadsRef.current = fn(threadsRef.current);
    setThreads(threadsRef.current);
  }, []);
  const activeRef = useRef<string | null>(null);
  const activate = useCallback((id: string | null) => {
    activeRef.current = id;
    setActiveId(id);
  }, []);
  const saveTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const abortRef = useRef<AbortController | null>(null);

  // ---- boot ------------------------------------------------------------------
  useEffect(() => {
    let alive = true;
    store.listThreads().then((list) => {
      if (alive) commit(() => list);
    }).catch(() => {
      if (alive) setStorageError("Could not load history from this browser.");
    }).finally(() => {
      if (alive) setLoaded(true);
    });
    getAskStatus().then((s) => {
      if (alive) setAskEnabled(s.enabled);
    }).catch(() => {
      if (alive) setAskEnabled(false);
    });
    return () => { alive = false; };
  }, [commit]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    const check = async () => {
      try {
        const health = await getHealth();
        if (!alive) return;
        setEngine({ status: "up", health });
        if (!formats) getFormats().then(setFormats).catch(() => {});
        if (!samples.length) getSamples().then(setSamples).catch(() => {});
        timer = setTimeout(check, 60_000);
      } catch (e) {
        if (!alive) return;
        setEngine({ status: "down", message: e instanceof Error ? e.message : String(e) });
        timer = setTimeout(check, 8_000);
      }
    };
    check();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- persistence ---------------------------------------------------------------
  const persist = useCallback((id: string, now = false) => {
    const timers = saveTimers.current;
    clearTimeout(timers.get(id));
    const write = () => {
      timers.delete(id);
      const t = threadsRef.current.find((x) => x.id === id);
      if (t) store.saveThread(t).catch(() => {
        setStorageError("Could not save a change to browser history. Download any results you need before leaving.");
      });
    };
    if (now) write();
    else timers.set(id, setTimeout(write, 400));
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

  const ensureThread = useCallback(
    (title: string): string => {
      const cur = activeRef.current;
      const existing = cur && threadsRef.current.find((t) => t.id === cur);
      if (existing) return existing.id;
      const now = Date.now();
      const t: Thread = { id: uid(), title, createdAt: now, updatedAt: now, turns: [] };
      commit((prev) => [t, ...prev]);
      activate(t.id);
      return t.id;
    },
    [activate, commit],
  );

  // ---- links across the thread ------------------------------------------------------
  const relink = useCallback(
    async (threadId: string, signal: AbortSignal) => {
      const th = threadsRef.current.find((t) => t.id === threadId);
      if (!th) return;
      const docs = threadDocs(th).map((d) => d.doc).filter(isReleased);
      const kinds = new Set(docs.flatMap((d) => d.data.batches.map((b) => b.kind)));
      const removeOld = (t: Thread): Thread => ({ ...t, turns: t.turns.filter((x) => x.kind !== "links") });
      if (th.turns.some((x) => x.kind === "links")) updateThread(threadId, removeOld, true);
      if (!kinds.has("statement") || !(kinds.has("settlement") || kinds.has("fira"))) {
        return;
      }
      if (engine.health?.link_available === false) throw new Error("Cross-file linking is unavailable on this engine.");
      const report = await linkDocs(docs, signal);
      signal.throwIfAborted();
      const names: Record<string, string> = {};
      for (const d of docs) names[d.file.sha256.slice(0, 12)] = d.file.name;
      const turn: LinksTurn = { id: uid(), kind: "links", at: Date.now(), report, names };
      updateThread(threadId, (t) => ({ ...t, turns: [...t.turns, turn] }), true);
    },
    [engine.health?.link_available, updateThread],
  );

  // Claim the operation synchronously. React's busy state can lag by a render.
  const operate = useCallback(async (
    kind: "run" | "ask" | "history",
    work: (signal: AbortSignal) => Promise<void>,
  ): Promise<boolean> => {
    if (!loaded || abortRef.current) return false;
    const controller = new AbortController();
    abortRef.current = controller;
    setOperation(kind);
    try {
      await work(controller.signal);
      return true;
    } finally {
      abortRef.current = null;
      setOperation(null);
    }
  }, [loaded]);

  const answerQuestion = useCallback(async (question: string, threadId: string, signal: AbortSignal) => {
    const before = threadsRef.current.find((t) => t.id === threadId);
    const history: { role: "user" | "assistant"; content: string }[] = [];
    let previousQuestion: string | undefined;
    for (const turn of before?.turns ?? []) {
      if (turn.kind === "user-ask") previousQuestion = turn.text;
      if (turn.kind === "answer") {
        if (previousQuestion && turn.state === "done" && !turn.error && turn.text.trim()) {
          history.push({ role: "user", content: previousQuestion }, { role: "assistant", content: turn.text });
        }
        previousQuestion = undefined;
      }
    }
    const userTurn: UserAskTurn = { id: uid(), kind: "user-ask", at: Date.now(), text: question };
    const answer: AnswerTurn = { id: uid(), kind: "answer", at: Date.now(), text: "", tools: [], state: "streaming" };
    appendTurns(threadId, [userTurn, answer]);
    try {
      for await (const event of ask({ question, history: trimHistory(history), docs: threadDocs(before) }, signal)) {
        if (event.type === "text") updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, text: a.text + event.text }));
        else if (event.type === "tool") updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({
          ...a, tools: [...a.tools, { name: event.name, summary: event.summary }],
        }));
      }
      signal.throwIfAborted();
      updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, state: "done" }), true);
    } catch (e) {
      updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({
        ...a, state: "error",
        error: signal.aborted ? "Answer stopped." : e instanceof Error ? e.message : "Something went wrong while answering.",
      }), true);
    }
  }, [appendTurns, updateTurn]);

  const sendAsk = useCallback((text: string) => {
    const question = text.trim();
    if (!question) return;
    return operate("ask", (signal) => answerQuestion(question, ensureThread(titleFor([], question)), signal));
  }, [answerQuestion, ensureThread, operate]);

  const sendRun = useCallback(
    async (files: File[], params: RunParams, perFile: Record<number, RunParams>, note?: string, label?: string) => {
      if (!files.length) return false;
      return operate("run", async (signal) => {
        const question = note?.trim();
        const threadId = ensureThread(titleFor(files, question ?? ""));
        const userTurn: UserRunTurn = {
          id: uid(), kind: "user-run", at: Date.now(),
          files: files.map((f) => ({ name: f.name, size: f.size })), params, note: label ?? (question || undefined),
        };
        rememberFiles(userTurn.id, files);
        const runTurn: RunTurn = {
          id: uid(), kind: "run", at: Date.now(), sourceTurnId: userTurn.id, state: "running",
          files: files.map<FileRun>((f, i) => ({
            index: i, name: f.name, size: f.size, stages: [], state: "queued", params: { ...params, ...perFile[i] },
          })),
        };
        appendTurns(threadId, [userTurn, runTurn]);
        const setFile = (i: number, fn: (f: FileRun) => FileRun, now = false) =>
          updateTurn<RunTurn>(threadId, runTurn.id, (t) => ({ ...t, files: t.files.map((f) => (f.index === i ? fn(f) : f)) }), now);
        let error: string | undefined;
        try {
          for await (const ev of runFiles(files, params, perFile, signal)) {
            if (ev.type === "started") setFile(ev.index, (f) => f.doc ? f : { ...f, state: "running" });
            else if (ev.type === "stage") setFile(ev.index, (f) => (f.stages.includes(ev.stage) ? f : { ...f, stages: [...f.stages, ev.stage] }));
            else if (ev.type === "done") setFile(ev.index, (f) => ({ ...f, state: "done", doc: ev.doc }), true);
          }
          signal.throwIfAborted();
        } catch (e) {
          error = signal.aborted ? "Run stopped." : e instanceof Error ? e.message : "The run failed.";
        }

        let hasReleased = false;
        updateTurn<RunTurn>(threadId, runTurn.id, (t) => {
          hasReleased = t.files.some((f) => isReleased(f.doc));
          error ??= t.files.some((f) => !f.doc)
            ? "The engine ended the run without a result for every file."
            : undefined;
          return {
            ...t, error, state: error ? "error" : "done",
            files: t.files.map((f) => (f.doc ? f : { ...f, state: "interrupted" })),
          };
        }, true);

        if (hasReleased) {
          try {
            setOperation("link");
            await relink(threadId, signal);
          } catch (e) {
            updateTurn<RunTurn>(threadId, runTurn.id, (t) => ({
              ...t, linkError: signal.aborted ? "Cross-file linking stopped."
                : e instanceof Error ? e.message : "Could not refresh cross-file links.",
            }), true);
          }
        }
        if (question && askEnabled && !error && !signal.aborted) {
          setOperation("ask");
          await answerQuestion(question, threadId, signal);
        }
      });
    },
    [answerQuestion, appendTurns, askEnabled, ensureThread, operate, relink, updateTurn],
  );

  /** Re-run one file from an earlier turn with changed params, as a new exchange in the thread. */
  const rerunFile = useCallback(
    async (run: RunTurn, index: number, override: RunParams): Promise<boolean> => {
      const file = recallFile(run.sourceTurnId, index);
      if (!file) return false;
      const prev = run.files.find((f) => f.index === index);
      const params = { ...(prev?.params ?? {}), ...override };
      const changed = paramSummary(override);
      return sendRun([file], params, {}, undefined, changed ? `Re-run with ${changed}` : "Retry interrupted file");
    },
    [sendRun],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const newThread = useCallback(() => {
    if (abortRef.current) return;
    activate(null);
  }, [activate]);

  const selectThread = useCallback((id: string) => {
    if (abortRef.current || !threadsRef.current.some((thread) => thread.id === id)) return;
    activate(id);
  }, [activate]);

  const removeThread = useCallback((id: string) => operate("history", async () => {
    const thread = threadsRef.current.find((t) => t.id === id);
    if (!thread) return;
    clearTimeout(saveTimers.current.get(id));
    saveTimers.current.delete(id);
    try {
      await store.deleteThread(id);
    } catch {
      setStorageError("Could not delete the thread from browser history.");
      return;
    }
    forgetThreadFiles(thread);
    commit((prev) => prev.filter((t) => t.id !== id));
    if (activeRef.current === id) activate(null);
  }), [activate, commit, operate]);

  const clearAll = useCallback(() => operate("history", async () => {
    saveTimers.current.forEach((timer) => clearTimeout(timer));
    saveTimers.current.clear();
    try {
      await store.clearThreads();
    } catch {
      setStorageError("Could not clear browser history.");
      return;
    }
    clearSessionFiles();
    commit(() => []);
    activate(null);
  }), [activate, commit, operate]);

  const active = useMemo(() => threads.find((t) => t.id === activeId), [threads, activeId]);

  return {
    loaded, threads, active, activeId, engine, formats, samples, askEnabled, busy: operation !== null, operation, storageError,
    sendRun, sendAsk, rerunFile, stop, newThread, selectThread, removeThread, clearAll,
  };
}

function trimHistory(h: { role: "user" | "assistant"; content: string }[]) {
  let out = h.slice(-HISTORY_MESSAGES);
  while (out.length && out[0]!.role !== "user") out = out.slice(1);
  return out;
}

export type Workspace = ReturnType<typeof useWorkspace>;
