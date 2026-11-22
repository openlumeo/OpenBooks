"use client";

import { BookOpen, FlaskConical, Plus, Trash2 } from "lucide-react";
import { BrandLockup } from "@/components/brand/brand-lockup";
import { ThemeToggle } from "@/components/brand/theme-toggle";
import { fmtAgo } from "@/lib/format";
import type { Workspace } from "@/lib/use-workspace";

export function Sidebar({ ws, open, onNavigate, onNew }: { ws: Workspace; open: boolean; onNavigate: () => void; onNew: () => void }) {
  const { engine } = ws;
  const h = engine.health;
  const status =
    engine.status === "up" && h
      ? `Engine ${h.engine_version} · OCR ${h.ocr_available ? "on" : "not installed"} · Model ${h.model_weights_present ? "ready" : "off"}`
      : engine.status === "down"
        ? "Engine unreachable"
        : "Checking engine";

  return (
    <aside className="ob-sidebar" data-open={open} aria-label="Threads">
      <div className="ob-sidebar-head">
        <a href="/app" aria-label="Open Books by Lumeo, new run" onClick={(e) => { e.preventDefault(); onNew(); }}>
          <BrandLockup />
        </a>
        <button
          type="button"
          className="btn btn-primary-landing btn-sm ob-new hero-cta-btn"
          onClick={onNew}
          disabled={ws.busy}
        >
          <span className="inline-flex items-center gap-2"><Plus size={15} /> New run</span>
          <span className="cta-dot" style={{ width: 7, height: 7 }} aria-hidden="true" />
        </button>
      </div>

      <nav className="ob-threads" aria-label="History">
        <div className="ob-threads-head">
          <span className="mono-label">History · this browser</span>
          {ws.threads.length > 0 && (
            <button
              type="button"
              className="copy-inline"
              onClick={() => {
                if (window.confirm("Delete every thread stored in this browser? Results cannot be recovered.")) ws.clearAll();
              }}
              disabled={ws.busy}
            >
              Clear
            </button>
          )}
        </div>
        {ws.loaded && ws.threads.length === 0 && (
          <p className="t-body-sm" style={{ padding: "4px 10px" }}>
            Runs you make are kept here, in this browser only. Files themselves are never stored.
          </p>
        )}
        <ul>
          {ws.threads.map((t) => {
            const runs = t.turns.filter((x) => x.kind === "run").flatMap((x) => (x.kind === "run" ? x.files : []));
            const ok = runs.filter((f) => f.doc?.status === "ok").length;
            const bad = runs.filter((f) => f.doc?.status === "refused").length;
            return (
              <li key={t.id}>
                <div
                  className="ob-thread"
                  role="button"
                  tabIndex={0}
                  aria-current={t.id === ws.activeId}
                  onClick={() => {
                    ws.selectThread(t.id);
                    onNavigate();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      ws.selectThread(t.id);
                      onNavigate();
                    }
                  }}
                >
                  <span className="ob-thread-title">{t.title}</span>
                  <span className="ob-thread-meta">
                    {fmtAgo(t.updatedAt)}
                    {runs.length > 0 && ` · ${ok} ok · ${bad} refused`}
                  </span>
                  <button
                    type="button"
                    className="icon-btn icon-btn--danger ob-thread-del"
                    aria-label={`Delete thread ${t.title}`}
                    disabled={ws.busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      ws.removeThread(t.id);
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="ob-sidebar-foot">
        <a className="ob-maturity" href="/docs">
          <BookOpen size={15} aria-hidden="true" />
          <span>Developer docs</span>
        </a>
        <div className="ob-foot-row">
          <span className="ob-status mono-label" role="status" title={engine.message ?? (h?.model_issue ? `${status}. Model: ${h.model_issue}` : status)}>
            <span className={`dot ${engine.status === "up" ? "dot--live" : engine.status === "down" ? "dot--bad" : ""}`} aria-hidden="true" />
            <span className="ob-status-text">{status}</span>
          </span>
          <ThemeToggle />
        </div>
        <a className="ob-maturity" href="/docs/model">
          <FlaskConical size={13} aria-hidden="true" />
          <span>Early release · tested on synthetic data only</span>
        </a>
      </div>
    </aside>
  );
}
