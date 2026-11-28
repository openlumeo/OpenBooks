"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, Menu, Upload } from "lucide-react";
import { BrandLockup } from "@/components/brand/brand-lockup";
import { Composer, type Pending } from "./composer";
import { EmptyState } from "./empty-state";
import { Sidebar } from "./sidebar";
import { AnswerView, LinksView, RunView, UserAsk, UserRun } from "./turns";
import { fetchSampleFile } from "@/lib/engine-client";
import { uid } from "@/lib/format";
import { MAX_FILE_BYTES } from "@/lib/guards";
import { threadDocs } from "@/lib/workspace/history";
import { useWorkspace, type Workspace as WorkspaceState } from "@/lib/workspace/use-workspace";
import type { RunParams, Sample } from "@/lib/types";

export function Workspace() {
  const ws = useWorkspace();
  const [drawer, setDrawer] = useState(false);
  const [draftVersion, setDraftVersion] = useState(0);

  return (
    <div className="ob-shell">
      <Sidebar
        ws={ws}
        open={drawer}
        onNavigate={() => setDrawer(false)}
        onNew={() => {
          if (ws.busy) return;
          ws.newThread();
          setDraftVersion((version) => version + 1);
          setDrawer(false);
        }}
      />
      {drawer && <div className="ob-scrim" onClick={() => setDrawer(false)} aria-hidden="true" />}
      <WorkspaceMain
        key={ws.activeId ?? `new-${draftVersion}`}
        ws={ws}
        drawer={drawer}
        openDrawer={() => setDrawer(true)}
      />
    </div>
  );
}

function WorkspaceMain({ ws, drawer, openDrawer }: { ws: WorkspaceState; drawer: boolean; openDrawer: () => void }) {
  const [pending, setPendingState] = useState<Pending[]>([]);
  const [params, setParams] = useState<RunParams>({});
  const [dragging, setDragging] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const dragDepth = useRef(0);

  useEffect(() => {
    if (!dragging) return;
    const reset = () => {
      dragDepth.current = 0;
      setDragging(false);
    };
    const onLeaveWindow = (e: DragEvent) => {
      if (!e.relatedTarget) reset();
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") reset();
    };
    window.addEventListener("dragend", reset);
    window.addEventListener("drop", reset);
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("dragleave", onLeaveWindow);
    return () => {
      window.removeEventListener("dragend", reset);
      window.removeEventListener("drop", reset);
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("dragleave", onLeaveWindow);
    };
  }, [dragging]);
  const sampleRequests = useRef(new Set<AbortController>());
  const attachInput = useRef<HTMLInputElement>(null);
  const inputLocked = ws.busy || !ws.loaded;

  useEffect(() => {
    const requests = sampleRequests.current;
    return () => requests.forEach((request) => request.abort());
  }, []);

  const setPending = useCallback((fn: (p: Pending[]) => Pending[]) => setPendingState(fn), []);
  const addFiles = useCallback(
    (files: File[]) => {
      if (!inputLocked && files.length) setPendingState((p) => [...p, ...files.map((file) => ({ id: uid(), file }))]);
    },
    [inputLocked],
  );

  const addSample = useCallback(
    async (s: Sample) => {
      if (inputLocked) return;
      const controller = new AbortController();
      sampleRequests.current.add(controller);
      setSampleError(null);
      try {
        const file = await fetchSampleFile(s, controller.signal);
        if (controller.signal.aborted) return;
        const own: RunParams = { currency: s.params.currency ?? "", opening: s.params.opening ?? "", ...s.params };
        setPendingState((p) => [...p, { id: uid(), file, params: own, sample: s.id }]);
      } catch (e) {
        if (!controller.signal.aborted) setSampleError(e instanceof Error ? e.message : "Could not load the sample.");
      } finally {
        sampleRequests.current.delete(controller);
      }
    },
    [inputLocked],
  );

  const turns = ws.active?.turns ?? [];
  const lastTurn = turns[turns.length - 1];
  const fingerprint = `${ws.activeId}:${turns.length}:${lastTurn?.kind === "answer" ? lastTurn.text.length : ""}:${
    lastTurn?.kind === "run"
      ? `${lastTurn.state}:${lastTurn.files.map((f) => f.stages.length + (f.doc ? 9 : 0)).join(",")}`
      : ""
  }`;

  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [fingerprint]);

  const send = (text: string) => {
    if (inputLocked) return;
    sampleRequests.current.forEach((request) => request.abort());
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
  const maxBytes = ws.engine.health?.max_bytes ?? ws.formats?.max_bytes ?? MAX_FILE_BYTES;
  const engineUp = ws.engine.status === "up";

  return (
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
        <button
          type="button"
          className="icon-btn icon-btn--boxed"
          aria-label="Open history"
          aria-expanded={drawer}
          onClick={openDrawer}
        >
          <Menu size={16} />
        </button>
        <BrandLockup markSize={22} />
        <a className="icon-btn icon-btn--boxed" href="/docs" aria-label="Developer docs">
          <BookOpen size={16} aria-hidden="true" />
        </a>
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
              The Open Books engine is not reachable. Start it with <code className="num">pnpm dev:engine</code>; this
              page reconnects on its own.
            </div>
          )}
          {sampleError && (
            <div className="ob-banner" role="alert" style={{ marginTop: 20 }}>
              <span className="dot dot--bad" aria-hidden="true" />
              {sampleError}
            </div>
          )}
          {ws.storageError && (
            <div className="ob-banner storage-banner" role="alert">
              {ws.storageError}
            </div>
          )}
          {turns.length === 0 ? (
            <EmptyState formats={ws.formats} onAttach={() => attachInput.current?.click()} disabled={inputLocked} />
          ) : (
            <div className="ob-conversation" aria-label={ws.active?.title}>
              {turns.map((t) => {
                switch (t.kind) {
                  case "user-run":
                    return <UserRun key={t.id} turn={t} />;
                  case "user-ask":
                    return <UserAsk key={t.id} turn={t} />;
                  case "run":
                    return (
                      <RunView
                        key={t.id}
                        turn={t}
                        recoveryDisabled={inputLocked || !engineUp}
                        onStop={ws.stop}
                        onRerun={ws.rerunFile}
                        onAttach={() => attachInput.current?.click()}
                      />
                    );
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
          attachInput={attachInput}
          pending={pending}
          setPending={setPending}
          params={params}
          setParams={setParams}
          samples={ws.samples}
          onAddSample={addSample}
          onAddFiles={addFiles}
          onSend={send}
          onStop={ws.stop}
          operation={ws.operation}
          locked={inputLocked}
          engineUp={engineUp}
          askEnabled={ws.askEnabled}
          allowed={allowed}
          maxBytes={maxBytes}
          modelAvailable={!!ws.engine.health?.model_weights_present}
          ocrIssue={ws.engine.health?.ocr_issue}
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
  );
}
