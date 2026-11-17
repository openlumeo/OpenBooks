"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, Upload } from "lucide-react";
import { BrandLockup } from "@/components/brand/brand-lockup";
import { Composer, type Pending } from "@/components/composer";
import { EmptyState } from "@/components/empty-state";
import { Sidebar } from "@/components/sidebar";
import { AnswerView, LinksView, RunView, UserAsk, UserRun } from "@/components/turns";
import { fetchSampleFile } from "@/lib/engine-client";
import { uid } from "@/lib/format";
import { threadDocs, useWorkspace } from "@/lib/use-workspace";
import type { RunParams, Sample } from "@/lib/types";

const DEFAULT_MAX = 20 * 1024 * 1024;

export function Workspace() {
  const ws = useWorkspace();
  const [pending, setPendingState] = useState<Pending[]>([]);
  const [params, setParams] = useState<RunParams>({});
  const [drawer, setDrawer] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const dragDepth = useRef(0);

  const setPending = useCallback((fn: (p: Pending[]) => Pending[]) => setPendingState(fn), []);
  const addFiles = useCallback((files: File[]) => {
    if (files.length) setPendingState((p) => [...p, ...files.map((file) => ({ id: uid(), file }))]);
  }, []);

  const addSample = useCallback(async (s: Sample) => {
    setSampleError(null);
    try {
      const file = await fetchSampleFile(s);
      // A sample brings its own params; blank values clear anything set for the run as a whole.
      const own: RunParams = { currency: s.params.currency ?? "", opening: s.params.opening ?? "", ...s.params };
      setPendingState((p) => [...p, { id: uid(), file, params: own, sample: s.id }]);
    } catch (e) {
      setSampleError(e instanceof Error ? e.message : "Could not load the sample.");
    }
  }, []);

  const turns = ws.active?.turns ?? [];
  const lastTurn = turns[turns.length - 1];
  const fingerprint = `${ws.activeId}:${turns.length}:${lastTurn?.kind === "answer" ? lastTurn.text.length : ""}:${
    lastTurn?.kind === "run" ? lastTurn.files.map((f) => f.stages.length + (f.doc ? 9 : 0)).join(",") : ""
  }`;

  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [fingerprint]);

  useEffect(() => {
    stick.current = true;
  }, [ws.activeId]);

  const send = (text: string) => {
    if (pending.length) {
      const files = pending.map((p) => p.file);
      const perFile: Record<number, RunParams> = {};
      pending.forEach((p, i) => {
        if (p.params) perFile[i] = p.params;
      });
      setPendingState([]);
      stick.current = true;
      ws.sendRun(files, params, perFile, text);
    } else if (text.trim()) {
      stick.current = true;
      ws.sendAsk(text);
    }
  };

  const allowed = ws.engine.health?.allowed_extensions ?? ws.formats?.allowed_extensions ?? [];
  const maxBytes = ws.engine.health?.max_bytes ?? DEFAULT_MAX;
  const engineUp = ws.engine.status === "up";

  return (
    <div className="ob-shell">
      <Sidebar ws={ws} open={drawer} onNavigate={() => setDrawer(false)} />
      {drawer && <div className="ob-scrim" onClick={() => setDrawer(false)} aria-hidden="true" />}

      <main
        className="ob-main"
        onDragEnter={(e) => {
          if (!e.dataTransfer.types.includes("Files")) return;
          dragDepth.current++;
          setDragging(true);
        }}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes("Files")) e.preventDefault();
        }}
        onDragLeave={() => {
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (dragDepth.current === 0) setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          dragDepth.current = 0;
          setDragging(false);
          if (!ws.busy) addFiles(Array.from(e.dataTransfer.files));
        }}
      >
        <header className="ob-topbar">
          <button type="button" className="icon-btn icon-btn--boxed" aria-label="Open history" aria-expanded={drawer} onClick={() => setDrawer(true)}>
            <Menu size={16} />
          </button>
          <BrandLockup markSize={22} />
          <span style={{ width: 40 }} />
        </header>

        <div
          className="ob-scroll"
          ref={scroller}
          onScroll={(e) => {
            const el = e.currentTarget;
            stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
          }}
        >
          <div className="ob-column" id="conversation" tabIndex={-1}>
            {ws.engine.status === "down" && (
              <div className="ob-banner" role="alert" style={{ marginTop: 20 }}>
                <span className="dot dot--bad" aria-hidden="true" />
                The Open Books engine is not reachable. Start it with <code className="num">pnpm dev:engine</code>; this page reconnects on its own.
              </div>
            )}
            {sampleError && (
              <div className="ob-banner" role="alert" style={{ marginTop: 20 }}>
                <span className="dot dot--bad" aria-hidden="true" />
                {sampleError}
              </div>
            )}
            {turns.length === 0 ? (
              <EmptyState formats={ws.formats} samples={ws.samples} onSample={addSample} engineUp={engineUp} />
            ) : (
              <div className="ob-conversation" aria-label={ws.active?.title}>
                {turns.map((t) => {
                  switch (t.kind) {
                    case "user-run":
                      return <UserRun key={t.id} turn={t} />;
                    case "user-ask":
                      return <UserAsk key={t.id} turn={t} />;
                    case "run":
                      return <RunView key={t.id} turn={t} busy={ws.busy} onStop={ws.stop} onRerun={(run, i, p) => ws.rerunFile(run, i, p)} />;
                    case "answer":
                      return <AnswerView key={t.id} turn={t} onStop={ws.stop} />;
                    case "links":
                      return <LinksView key={t.id} turn={t} />;
                  }
                })}
              </div>
            )}
          </div>
        </div>

        <div className="ob-column">
          <Composer
            pending={pending}
            setPending={setPending}
            params={params}
            setParams={setParams}
            samples={ws.samples}
            onAddSample={addSample}
            onAddFiles={addFiles}
            onSend={send}
            onStop={ws.stop}
            busy={ws.busy}
            engineUp={engineUp}
            askEnabled={ws.askEnabled}
            allowed={allowed}
            maxBytes={maxBytes}
            modelAvailable={!!ws.engine.health?.model_weights_present}
            modelIssue={ws.engine.health?.model_issue}
            hasDocs={threadDocs(ws.active).length > 0}
          />
        </div>

        {dragging && (
          <div className="dropzone" aria-hidden="true">
            <div className="dropzone-inner">
              <Upload size={22} />
              <span className="t-card-title">Drop to add files</span>
              <span className="mono-label">CSV · OFX · MT940 · PDF · scans · XLSX</span>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
