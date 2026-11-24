"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ask, getAskStatus, linkDocs, runFiles } from "../engine-client";
import { paramSummary, uid } from "../format";
import { clearSessionFiles, forgetThreadFiles, recallFile, rememberFiles } from "../session-files";
import * as store from "../store";
import {
  isReleased,
  type AnswerTurn,
  type FileRun,
  type LinksTurn,
  type RunParams,
  type RunTurn,
  type UserAskTurn,
  type UserRunTurn,
} from "../types";
import { priorExchanges, threadDocs, titleFor, trimHistory } from "./history";
import { useEngineStatus } from "./use-engine-status";
import { useThreadStore } from "./use-thread-store";

type Operation = "run" | "link" | "ask" | "history";

export function useWorkspace() {
  const {
    threads,
    loaded,
    activeId,
    storageError,
    setStorageError,
    threadsRef,
    activeRef,
    saveTimers,
    commit,
    activate,
    updateThread,
    updateTurn,
    appendTurns,
    ensureThread,
  } = useThreadStore();
  const { engine, formats, samples } = useEngineStatus();
  const [askEnabled, setAskEnabled] = useState<boolean | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let alive = true;
    getAskStatus()
      .then((s) => {
        if (alive) setAskEnabled(s.enabled);
      })
      .catch(() => {
        if (alive) setAskEnabled(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const relink = useCallback(
    async (threadId: string, signal: AbortSignal) => {
      const th = threadsRef.current.find((t) => t.id === threadId);
      if (!th) return;
      const docs = threadDocs(th)
        .map((d) => d.doc)
        .filter(isReleased);
      const kinds = new Set(docs.flatMap((d) => d.data.batches.map((b) => b.kind)));
      const removeOld = (t: typeof th): typeof th => ({ ...t, turns: t.turns.filter((x) => x.kind !== "links") });
      if (th.turns.some((x) => x.kind === "links")) updateThread(threadId, removeOld, true);
      if (!kinds.has("statement") || !(kinds.has("settlement") || kinds.has("fira"))) return;
      if (engine.health?.link_available === false) throw new Error("Cross-file linking is unavailable on this engine.");
      const report = await linkDocs(docs, signal);
      signal.throwIfAborted();
      const names: Record<string, string> = {};
      for (const d of docs) names[d.file.sha256.slice(0, 12)] = d.file.name;
      const turn: LinksTurn = { id: uid(), kind: "links", at: Date.now(), report, names };
      updateThread(threadId, (t) => ({ ...t, turns: [...t.turns, turn] }), true);
    },
    [engine.health?.link_available, threadsRef, updateThread],
  );

  const operate = useCallback(
    async (kind: Exclude<Operation, "link">, work: (signal: AbortSignal) => Promise<void>): Promise<boolean> => {
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
    },
    [loaded],
  );

  const answerQuestion = useCallback(
    async (question: string, threadId: string, signal: AbortSignal) => {
      const before = threadsRef.current.find((t) => t.id === threadId);
      const userTurn: UserAskTurn = { id: uid(), kind: "user-ask", at: Date.now(), text: question };
      const answer: AnswerTurn = { id: uid(), kind: "answer", at: Date.now(), text: "", tools: [], state: "streaming" };
      appendTurns(threadId, [userTurn, answer]);
      try {
        const request = { question, history: trimHistory(priorExchanges(before)), docs: threadDocs(before) };
        for await (const event of ask(request, signal)) {
          if (event.type === "text")
            updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, text: a.text + event.text }));
          else if (event.type === "tool")
            updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({
              ...a,
              tools: [...a.tools, { name: event.name, summary: event.summary }],
            }));
        }
        signal.throwIfAborted();
        updateTurn<AnswerTurn>(threadId, answer.id, (a) => ({ ...a, state: "done" }), true);
      } catch (e) {
        updateTurn<AnswerTurn>(
          threadId,
          answer.id,
          (a) => ({
            ...a,
            state: "error",
            error: signal.aborted
              ? "Answer stopped."
              : e instanceof Error
                ? e.message
                : "Something went wrong while answering.",
          }),
          true,
        );
      }
    },
    [appendTurns, threadsRef, updateTurn],
  );

  const sendAsk = useCallback(
    (text: string) => {
      const question = text.trim();
      if (!question) return;
      return operate("ask", (signal) => answerQuestion(question, ensureThread(titleFor([], question)), signal));
    },
    [answerQuestion, ensureThread, operate],
  );

  const sendRun = useCallback(
    async (files: File[], params: RunParams, perFile: Record<number, RunParams>, note?: string, label?: string) => {
      if (!files.length) return false;
      return operate("run", async (signal) => {
        const question = note?.trim();
        const threadId = ensureThread(titleFor(files, question ?? ""));
        const userTurn: UserRunTurn = {
          id: uid(),
          kind: "user-run",
          at: Date.now(),
          files: files.map((f) => ({ name: f.name, size: f.size })),
          params,
          note: label ?? (question || undefined),
        };
        rememberFiles(userTurn.id, files);
        const runTurn: RunTurn = {
          id: uid(),
          kind: "run",
          at: Date.now(),
          sourceTurnId: userTurn.id,
          state: "running",
          files: files.map<FileRun>((f, i) => ({
            index: i,
            name: f.name,
            size: f.size,
            stages: [],
            state: "queued",
            params: { ...params, ...perFile[i] },
          })),
        };
        appendTurns(threadId, [userTurn, runTurn]);
        const setFile = (i: number, fn: (f: FileRun) => FileRun, now = false) =>
          updateTurn<RunTurn>(
            threadId,
            runTurn.id,
            (t) => ({ ...t, files: t.files.map((f) => (f.index === i ? fn(f) : f)) }),
            now,
          );
        let error = await streamRun(files, params, perFile, signal, setFile);

        let hasReleased = false;
        updateTurn<RunTurn>(
          threadId,
          runTurn.id,
          (t) => {
            hasReleased = t.files.some((f) => isReleased(f.doc));
            error ??= t.files.some((f) => !f.doc)
              ? "The engine ended the run without a result for every file."
              : undefined;
            return {
              ...t,
              error,
              state: error ? "error" : "done",
              files: t.files.map((f) => (f.doc ? f : { ...f, state: "interrupted" })),
            };
          },
          true,
        );

        if (hasReleased) {
          try {
            setOperation("link");
            await relink(threadId, signal);
          } catch (e) {
            updateTurn<RunTurn>(
              threadId,
              runTurn.id,
              (t) => ({
                ...t,
                linkError: signal.aborted
                  ? "Cross-file linking stopped."
                  : e instanceof Error
                    ? e.message
                    : "Could not refresh cross-file links.",
              }),
              true,
            );
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

  const selectThread = useCallback(
    (id: string) => {
      if (abortRef.current || !threadsRef.current.some((thread) => thread.id === id)) return;
      activate(id);
    },
    [activate, threadsRef],
  );

  const removeThread = useCallback(
    (id: string) =>
      operate("history", async () => {
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
      }),
    [activate, activeRef, commit, operate, saveTimers, setStorageError, threadsRef],
  );

  const clearAll = useCallback(
    () =>
      operate("history", async () => {
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
      }),
    [activate, commit, operate, saveTimers, setStorageError],
  );

  const active = useMemo(() => threads.find((t) => t.id === activeId), [threads, activeId]);

  return {
    loaded,
    threads,
    active,
    activeId,
    engine,
    formats,
    samples,
    askEnabled,
    busy: operation !== null,
    operation,
    storageError,
    sendRun,
    sendAsk,
    rerunFile,
    stop,
    newThread,
    selectThread,
    removeThread,
    clearAll,
  };
}

type SetFile = (i: number, fn: (f: FileRun) => FileRun, now?: boolean) => void;

async function streamRun(
  files: File[],
  params: RunParams,
  perFile: Record<number, RunParams>,
  signal: AbortSignal,
  setFile: SetFile,
): Promise<string | undefined> {
  try {
    for await (const ev of runFiles(files, params, perFile, signal)) {
      if (ev.type === "started") setFile(ev.index, (f) => (f.doc ? f : { ...f, state: "running" }));
      else if (ev.type === "stage")
        setFile(ev.index, (f) => (f.stages.includes(ev.stage) ? f : { ...f, stages: [...f.stages, ev.stage] }));
      else if (ev.type === "done") setFile(ev.index, (f) => ({ ...f, state: "done", doc: ev.doc }), true);
    }
    signal.throwIfAborted();
    return undefined;
  } catch (e) {
    return signal.aborted ? "Run stopped." : e instanceof Error ? e.message : "The run failed.";
  }
}

export type Workspace = ReturnType<typeof useWorkspace>;
