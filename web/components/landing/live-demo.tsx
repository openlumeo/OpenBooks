"use client";

import { useCallback, useEffect, useReducer, useRef, useState, type DragEvent } from "react";
import { Check, FileText, X } from "lucide-react";
import { STAGES } from "@/lib/stages";
import { parseSSE } from "@/lib/sse";
import type { EngineDoc, Sample, Stage } from "@/lib/types";
import { ReconPanel, ReconRow } from "./reconciliation";
import { DEMO_SAMPLES, REPLAYS, isDemoSampleId, verdictFromDoc, type DemoSampleId, type DemoVerdict } from "./live-demo-data";
import styles from "./live-demo.module.css";

const CALL_TIMEOUT_MS = 2500;
const REPLAY_STEP_MS = 420;
const TICK_MS = 100;
const REPLAY_FAILED = "The demo could not finish. Run it again.";

type Status = "idle" | "running" | "done" | "error";
type Mode = "live" | "replay";
type StageState = "pending" | "active" | "done" | "stopped";

type State = {
  status: Status;
  mode: Mode | null;
  sampleId: DemoSampleId;
  seen: Stage[];
  verdict: DemoVerdict | null;
  elapsedMs: number;
  announce: string;
  error: string | null;
};

type Action =
  | { type: "select"; sampleId: DemoSampleId }
  | { type: "start"; sampleId: DemoSampleId; mode: Mode }
  | { type: "stage"; stage: Stage }
  | { type: "tick"; elapsedMs: number }
  | { type: "verdict"; verdict: DemoVerdict; elapsedMs: number }
  | { type: "fail"; elapsedMs: number };

const INITIAL: State = {
  status: "idle",
  mode: null,
  sampleId: "ok_bank_csv",
  seen: [],
  verdict: null,
  elapsedMs: 0,
  announce: "",
  error: null,
};

function stageLabel(stage: Stage): string {
  return STAGES.find((s) => s.id === stage)?.label ?? stage;
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "select":
      return state.status === "running" ? state : { ...state, sampleId: action.sampleId };
    case "start":
      return {
        ...INITIAL,
        status: "running",
        mode: action.mode,
        sampleId: action.sampleId,
        announce: action.mode === "live" ? "Running on the engine." : "The engine is not reachable. Replaying a recorded run.",
      };
    case "stage": {
      const stage: Stage = action.stage === "validate" ? "balance" : action.stage;
      if (state.seen.includes(stage)) return state;
      return { ...state, seen: [...state.seen, stage], announce: `${stageLabel(stage)} passed.` };
    }
    case "tick":
      return state.status === "running" ? { ...state, elapsedMs: action.elapsedMs } : state;
    case "verdict": {
      const v = action.verdict;
      const announce =
        v.kind === "released"
          ? `Released. ${v.rowCount} rows tie out. Verdict in ${action.elapsedMs} milliseconds.`
          : `Refused, ${v.code}. ${v.message}`;
      return { ...state, status: "done", verdict: v, elapsedMs: action.elapsedMs, announce, error: null };
    }
    case "fail":
      return { ...state, status: "error", verdict: null, elapsedMs: action.elapsedMs, error: REPLAY_FAILED, announce: REPLAY_FAILED };
  }
}

function stageStates(seen: Stage[], verdict: DemoVerdict | null, running: boolean): StageState[] {
  if (verdict?.kind === "refused") {
    const stop = STAGES.findIndex((s) => s.id === verdict.stopAt);
    return STAGES.map((_, i) => (i < stop ? "done" : i === stop ? "stopped" : "pending"));
  }
  if (verdict?.kind === "released") return STAGES.map(() => "done");
  const firstOpen = STAGES.findIndex((s) => !seen.includes(s.id));
  return STAGES.map((s, i) => (seen.includes(s.id) ? "done" : running && i === firstOpen ? "active" : "pending"));
}

function timedFetch(url: string, init: RequestInit, parent: AbortSignal): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), CALL_TIMEOUT_MS);
  parent.addEventListener("abort", () => ctrl.abort(), { once: true });
  return fetch(url, { ...init, signal: ctrl.signal }).finally(() => clearTimeout(timer));
}

async function runLive(sampleId: DemoSampleId, signal: AbortSignal, onStart: () => void, onStage: (stage: Stage) => void): Promise<DemoVerdict> {
  const health = await timedFetch("/api/engine/health", { cache: "no-store" }, signal);
  if (!health.ok) throw new Error(`health ${health.status}`);
  await health.json();

  const listRes = await timedFetch("/api/engine/samples", { cache: "no-store" }, signal);
  if (!listRes.ok) throw new Error(`samples ${listRes.status}`);
  const { samples } = (await listRes.json()) as { samples: Sample[] };
  const sample = samples.find((s) => s.id === sampleId);
  if (!sample) throw new Error("sample not in catalog");

  const bytesRes = await timedFetch(`/api/engine/samples/${encodeURIComponent(sampleId)}`, { cache: "no-store" }, signal);
  if (!bytesRes.ok) throw new Error(`sample ${bytesRes.status}`);
  const file = new File([await bytesRes.blob()], sample.filename, { type: "text/csv" });

  const fd = new FormData();
  fd.append("files", file, file.name);
  fd.append("params", JSON.stringify(sample.params));
  const res = await timedFetch("/api/runs", { method: "POST", body: fd }, signal);
  if (!res.ok || !res.body || res.status === 202) throw new Error(`runs ${res.status}`);

  onStart();
  let doc: EngineDoc | null = null;
  for await (const ev of parseSSE(res.body)) {
    if (ev.event === "file.stage") {
      onStage((JSON.parse(ev.data) as { stage: Stage }).stage);
    } else if (ev.event === "file.done") {
      doc = (JSON.parse(ev.data) as { doc: EngineDoc }).doc;
    } else if (ev.event === "run.error" || ev.event === "error") {
      throw new Error("engine error");
    }
  }
  if (!doc) throw new Error("run ended without a verdict");
  return verdictFromDoc(doc);
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(signal.reason);
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export function LiveDemo({ autoplay = false }: { autoplay?: boolean }) {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const [dropActive, setDropActive] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const tickRef = useRef<number | null>(null);
  const autoplayed = useRef(false);
  const touched = useRef(false);

  const stopClock = useCallback(() => {
    if (tickRef.current !== null) window.clearInterval(tickRef.current);
    tickRef.current = null;
  }, []);

  const run = useCallback(
    (sampleId: DemoSampleId) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const { signal } = controller;
      const clock = { t0: performance.now() };
      const elapsed = () => Math.round(performance.now() - clock.t0);
      const startClock = () => {
        stopClock();
        tickRef.current = window.setInterval(() => dispatch({ type: "tick", elapsedMs: elapsed() }), TICK_MS);
      };

      startClock();
      dispatch({ type: "start", sampleId, mode: "live" });

      const replay = async () => {
        clock.t0 = performance.now();
        startClock();
        dispatch({ type: "start", sampleId, mode: "replay" });
        const step = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : REPLAY_STEP_MS;
        const recorded = REPLAYS[sampleId];
        for (const stage of recorded.stagesReached) {
          await sleep(step, signal);
          dispatch({ type: "stage", stage });
        }
        await sleep(step, signal);
        stopClock();
        dispatch({ type: "verdict", verdict: recorded.verdict, elapsedMs: elapsed() });
      };

      void (async () => {
        try {
          const verdict = await runLive(sampleId, signal, () => undefined, (stage) => dispatch({ type: "stage", stage }));
          if (signal.aborted) return;
          stopClock();
          dispatch({ type: "verdict", verdict, elapsedMs: elapsed() });
        } catch {
          if (signal.aborted) return;
          try {
            await replay();
          } catch {
            if (!signal.aborted) {
              stopClock();
              dispatch({ type: "fail", elapsedMs: elapsed() });
            }
          }
        }
      })();
    },
    [stopClock],
  );

  const runFromUser = useCallback(
    (sampleId: DemoSampleId) => {
      touched.current = true;
      run(sampleId);
    },
    [run],
  );

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (tickRef.current !== null) window.clearInterval(tickRef.current);
    };
  }, []);

  useEffect(() => {
    if (!autoplay) return;
    const el = rootRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting) || autoplayed.current) return;
        autoplayed.current = true;
        io.disconnect();
        if (!touched.current) run("ok_bank_csv");
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [autoplay, run]);

  const { status, mode, sampleId, seen, verdict, elapsedMs, announce, error } = state;
  const busy = status === "running";
  const states = stageStates(seen, verdict, busy);

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    if (busy || !e.dataTransfer.types.includes("text/plain")) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setDropActive(true);
  };
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDropActive(false);
    const id = e.dataTransfer.getData("text/plain");
    if (busy || !isDemoSampleId(id)) return;
    dispatch({ type: "select", sampleId: id });
    runFromUser(id);
  };

  const replaying = mode === "replay";
  const modeLine = busy
    ? replaying
      ? "Replaying a recorded run"
      : "Running on the engine"
    : status === "done"
      ? replaying
        ? "Replaying a recorded run"
        : "Engine run"
      : status === "error"
        ? "Not run"
        : "Ready";

  const idleText = status === "idle";

  return (
    <div ref={rootRef} className={styles.demo} data-status={status}>
      <div className={styles.bar}>
        <span className={styles.barTitle}>Open Books · Workspace</span>
        <span className={styles.barMeta}>{busy ? "Running" : status === "done" ? "Verdict" : "Idle"}</span>
      </div>

      <div className={styles.body}>
        <div
          className={[styles.input, dropActive ? styles.dropActive : ""].filter(Boolean).join(" ")}
          onDragOver={onDragOver}
          onDragLeave={() => setDropActive(false)}
          onDrop={onDrop}
        >
          <span className={styles.label}>Input</span>
          <div className={styles.chips} role="group" aria-label="Samples">
            {DEMO_SAMPLES.map((s) => (
              <button
                key={s.id}
                type="button"
                className={styles.chip}
                aria-pressed={sampleId === s.id}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData("text/plain", s.id);
                  e.dataTransfer.effectAllowed = "copy";
                }}
                onClick={() => dispatch({ type: "select", sampleId: s.id })}
              >
                <FileText size={15} strokeWidth={1.75} aria-hidden="true" />
                <span>{s.chip}</span>
              </button>
            ))}
          </div>
          <p className={styles.dropHint}>Drag a sample here to run it</p>
          <button type="button" className={`btn btn-primary-landing ${styles.run}`} disabled={busy} onClick={() => runFromUser(sampleId)}>
            {busy ? "Running" : verdict ? "Run again" : "Run"}
          </button>
        </div>

        <div className={styles.output}>
          <ol className={styles.stages} aria-label="Pipeline stages">
            {STAGES.map((s, i) => {
              const st = states[i] ?? "pending";
              const word = st === "done" ? "passed" : st === "stopped" ? "stopped here" : st === "active" ? "in progress" : "not reached";
              return (
                <li key={s.id} className={styles.stage} data-state={st} title={s.hint}>
                  <span className={styles.mark} aria-hidden="true">
                    {st === "done" ? <Check size={11} strokeWidth={2.25} /> : null}
                    {st === "stopped" ? <X size={11} strokeWidth={2.25} /> : null}
                    {st === "active" ? <span className={styles.pulse} /> : null}
                  </span>
                  <span className={styles.stageName}>{s.label}</span>
                  <span className={styles.srOnly}>: {word}</span>
                </li>
              );
            })}
          </ol>

          <div className={styles.result}>
            {idleText ? (
              <p className={styles.idle}>Pick a statement and run it. The stages light as the engine passes them, and the verdict appears here.</p>
            ) : null}
            {busy && !verdict ? <p className={styles.idle}>Reading the file and checking its arithmetic.</p> : null}
            {status === "error" ? <p className={styles.error}>{error}</p> : null}

            {verdict?.kind === "released" ? (
              <div className={styles.verdict}>
                <div className={styles.stampRow}>
                  <span className={styles.stamp}>Released</span>
                  <span className={styles.figures}>
                    Opening {verdict.opening} · Closing {verdict.closing} {verdict.currency}
                  </span>
                </div>
                <ReconPanel title={`Ledger · first ${verdict.rows.length} of ${verdict.rowCount}`}>
                  {verdict.rows.map((r) => (
                    <ReconRow key={r.id} cells={[r.date, `${r.direction} ${r.description}`.trim(), r.amount, r.balance]} />
                  ))}
                </ReconPanel>
                {verdict.hiddenRowCount > 0 ? <p className={styles.more}>+ {verdict.hiddenRowCount} more rows</p> : null}
                <ReconPanel title="Checks">
                  {verdict.checks.slice(0, 4).map((c) => (
                    <ReconRow
                      key={c.id}
                      state={c.passed ? "matched" : "unmatched"}
                      cells={[`${c.id} ${c.rule}`, c.independent ? "Independent" : "", c.passed ? "Pass" : "Fail"]}
                    />
                  ))}
                </ReconPanel>
              </div>
            ) : null}

            {verdict?.kind === "refused" ? (
              <div className={styles.verdict}>
                <ReconRow state="unmatched" cells={[`Refused · ${verdict.code}`, `Stopped at ${stageLabel(verdict.stopAt)}`]} />
                <p className={styles.message}>{verdict.message}</p>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className={styles.foot}>
        <span>{modeLine}</span>
        <span className={styles.elapsed}>{idleText ? "" : `${elapsedMs} ms`}</span>
      </div>

      <p className={styles.srOnly} aria-live="polite">
        {announce}
      </p>
      <noscript>
        <p className={styles.noscript}>Running a file needs JavaScript. The workspace runs the same engine without this demo.</p>
      </noscript>
    </div>
  );
}
