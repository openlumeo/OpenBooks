"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, ask, getAskStatus, getFormats, getHealth, getSamples, linkDocs, runFiles } from "./engine-client";
import { uid } from "./format";
import { fileKeys } from "./query";
import { recallFile, rememberFiles } from "./session-files";
import * as store from "./store";
import {
  isReleased,
  type AnswerTurn,
  type EngineDoc,
  type FileRun,
  type Formats,
  type Health,
  type LinksTurn,
  type ReleasedDoc,
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
  const [busy, setBusy] = useState(false);

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
    store.listThreads().then((list) => {
      commit(() => list);
      setLoaded(true);
    }).catch(() => setLoaded(true));
    getAskStatus().then((s) => setAskEnabled(s.enabled)).catch(() => setAskEnabled(false));
  }, []);

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
      const t = threadsRef.current.find((x) => x.id === id);
      if (t) store.saveThread(t).catch(() => {});
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
      store.saveThread(t).catch(() => {});
      return t.id;
    },
    [activate, commit],
  );

  // ---- links across the thread ------------------------------------------------------
  const relink = useCallback(
    async (threadId: string) => {
      const th = threadsRef.current.find((t) => t.id === threadId);
      if (!th) return;
      const docs = threadDocs(th).map((d) => d.doc).filter(isReleased) as ReleasedDoc[];
      const kinds = new Set(docs.flatMap((d) => d.data.batches.map((b) => b.kind)));
      const removeOld = (t: Thread): Thread => ({ ...t, turns: t.turns.filter((x) => x.kind !== "links") });
      if (!kinds.has("statement") || !(kinds.has("settlement") || kinds.has("fira"))) {
        if (th.turns.some((x) => x.kind === "links")) updateThread(threadId, removeOld, true);
        return;
      }
      try {
        const report = await linkDocs(docs);
        const names: Record<string, string> = {};
        for (const d of docs) names[d.file.sha256.slice(0, 12)] = d.file.name;
        const turn: LinksTurn = { id: uid(), kind: "links", at: Date.now(), report, names };
        updateThread(threadId, (t) => ({ ...removeOld(t), turns: [...removeOld(t).turns, turn] }), true);
      } catch {
        // Linking is an extra; a failure leaves the runs untouched.
      }
    },
    [updateThread],
  );

  // ---- ask ---------------------------------------------------------------------------
  const sendAsk = useCallback(
    async (text: string, threadIdIn?: string) => {
      const question = text.trim();
      if (!question) return;
      const threadId = threadIdIn ?? ensureThread(titleFor([], question));
      const before = threadsRef.current.find((t) => t.id === threadId);
      const history: { role: "user" | "assistant"; content: string }[] = [];
      for (const t of before?.turns ?? []) {
        if (t.kind === "user-ask") history.push({ role: "user", content: t.text });
        else if (t.kind === "answer" && t.state === "done" && t.text.trim()) history.push({ role: "assistant", content: t.text });
      }
      const userTurn: UserAskTurn = { id: uid(), kind: "user-ask", at: Date.now(), text: question };
      const answer: AnswerTurn = { id: uid(), kind: "answer", at: Date.now(), text: "", tools: [], state: "streaming" };
      appendTurns(threadId, [userTurn, answer]);
      setBusy(true);
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        for await (const ev of ask({ question, history: trimHistory(history), docs: threadDocs(before) }, ctrl.signal)) {
          if (ev.type === "text") updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, text: a.text + ev.text }));
          else if (ev.type === "tool") updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, tools: [...a.tools, { name: ev.name, summary: ev.summary }] }));
          else if (ev.type === "error") updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, error: ev.message }));
        }
        updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, state: a.error && !a.text ? "error" : "done" }), true);
      } catch (e) {
        const aborted = ctrl.signal.aborted;
        updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({
          ...a,
          state: aborted && a.text ? "done" : "error",
          error: aborted ? "Stopped." : e instanceof Error ? e.message : "Something went wrong while answering.",
        }), true);
      } finally {
        abortRef.current = null;
        setBusy(false);
      }
    },
    [appendTurns, ensureThread, updateTurn],
  );

  // ---- run -----------------------------------------------------------------------------
  const sendRun = useCallback(
    async (files: File[], params: RunParams, perFile: Record<number, RunParams>, note?: string, label?: string) => {
      if (!files.length) return;
      const threadId = ensureThread(titleFor(files, note ?? ""));
      const userTurn: UserRunTurn = {
        id: uid(), kind: "user-run", at: Date.now(),
        files: files.map((f) => ({ name: f.name, size: f.size })), params, note: label ?? (note?.trim() || undefined),
      };
      rememberFiles(userTurn.id, files);
      const runTurn: RunTurn = {
        id: uid(), kind: "run", at: Date.now(), sourceTurnId: userTurn.id, state: "running",
        files: files.map<FileRun>((f, i) => ({ index: i, name: f.name, size: f.size, stages: [], state: "queued", params: { ...params, ...perFile[i] } })),
      };
      appendTurns(threadId, [userTurn, runTurn]);
      setBusy(true);
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const setFile = (i: number, fn: (f: FileRun) => FileRun) =>
        updateTurn<RunTurn>(threadId, runTurn.id, (t) => ({ ...t, files: t.files.map((f) => (f.index === i ? fn(f) : f)) }));
      try {
        for await (const ev of runFiles(files, params, perFile, ctrl.signal)) {
          if (ev.type === "started") setFile(ev.index, (f) => ({ ...f, state: "running" }));
          else if (ev.type === "stage") setFile(ev.index, (f) => (f.stages.includes(ev.stage) ? f : { ...f, stages: [...f.stages, ev.stage] }));
          else if (ev.type === "done") setFile(ev.index, (f) => ({ ...f, state: "done", doc: ev.doc }));
          else if (ev.type === "error") updateTurn<RunTurn>(threadId, runTurn.id, (t) => ({ ...t, state: "error", error: ev.message }));
        }
      } catch (e) {
        const msg = ctrl.signal.aborted ? "Stopped." : e instanceof ApiError || e instanceof Error ? e.message : "The run failed.";
        updateTurn<RunTurn>(threadId, runTurn.id, (t) => ({ ...t, state: "error", error: msg }));
      } finally {
        updateTurn<RunTurn>(threadId, runTurn.id, (t) => ({
          ...t,
          state: t.state === "error" ? "error" : "done",
          files: t.files.map((f) => (f.doc ? f : { ...f, state: "interrupted" })),
        }), true);
        abortRef.current = null;
        setBusy(false);
      }
      await relink(threadId);
      if (note?.trim() && askEnabled) await sendAsk(note, threadId);
    },
    [appendTurns, askEnabled, ensureThread, relink, sendAsk, updateTurn],
  );

  /** Re-run one file from an earlier turn with changed params, as a new exchange in the thread. */
  const rerunFile = useCallback(
    async (run: RunTurn, index: number, override: RunParams): Promise<boolean> => {
      const file = recallFile(run.sourceTurnId, index);
      if (!file) return false;
      const prev = run.files.find((f) => f.index === index);
      const params = { ...(prev?.params ?? {}), ...override };
      const changed = Object.entries(override).map(([k, v]) => `${k} ${v}`).join(", ");
      await sendRun([file], params, {}, undefined, `Re-run with ${changed}`);
      return true;
    },
    [sendRun],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const newThread = useCallback(() => {
    if (busy) return;
    activate(null);
  }, [activate, busy]);

  const selectThread = useCallback((id: string) => {
    if (busy) return;
    activate(id);
  }, [activate, busy]);

  const removeThread = useCallback(async (id: string) => {
    clearTimeout(saveTimers.current.get(id));
    await store.deleteThread(id);
    commit((prev) => prev.filter((t) => t.id !== id));
    if (activeRef.current === id) activate(null);
  }, [activate, commit]);

  const clearAll = useCallback(async () => {
    saveTimers.current.forEach((t) => clearTimeout(t));
    await store.clearThreads();
    commit(() => []);
    activate(null);
  }, [activate, commit]);

  const active = useMemo(() => threads.find((t) => t.id === activeId), [threads, activeId]);

  return {
    loaded, threads, active, activeId, engine, formats, samples, askEnabled, busy,
    sendRun, sendAsk, rerunFile, stop, newThread, selectThread, removeThread, clearAll,
  };
}

function trimHistory(h: { role: "user" | "assistant"; content: string }[]) {
  let out = h.slice(-HISTORY_MESSAGES);
  while (out.length && out[0]!.role !== "user") out = out.slice(1);
  return out;
}

export type Workspace = ReturnType<typeof useWorkspace>;
