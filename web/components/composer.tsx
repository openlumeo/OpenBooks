"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ArrowUp, FlaskConical, Paperclip, SlidersHorizontal, Square, X } from "lucide-react";
import { fmtBytes, paramSummary } from "@/lib/format";
import type { RunParams, Sample } from "@/lib/types";

export const MAX_FILES = 20;

export type Pending = { id: string; file: File; params?: RunParams; sample?: string };

export type ComposerProps = {
  pending: Pending[];
  setPending: (fn: (p: Pending[]) => Pending[]) => void;
  params: RunParams;
  setParams: (p: RunParams) => void;
  samples: Sample[];
  onAddSample: (s: Sample) => void;
  onAddFiles: (files: File[]) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  busy: boolean;
  engineUp: boolean;
  askEnabled: boolean | null;
  allowed: string[];
  maxBytes: number;
  modelAvailable: boolean;
  modelIssue?: string | null;
  hasDocs: boolean;
};

const ext = (name: string) => (name.includes(".") ? name.slice(name.lastIndexOf(".")).toLowerCase() : "");

export function problemsFor(pending: Pending[], allowed: string[], maxBytes: number): string | null {
  if (pending.length > MAX_FILES) return `At most ${MAX_FILES} files per run. Remove ${pending.length - MAX_FILES}.`;
  const bad = pending.filter((p) => allowed.length && !allowed.includes(ext(p.file.name)));
  if (bad.length) return `${bad[0]!.file.name} is not a supported type. Accepted: ${allowed.join(" ")}.`;
  const big = pending.filter((p) => p.file.size > maxBytes);
  if (big.length) return `${big[0]!.file.name} is over the ${fmtBytes(maxBytes)} limit.`;
  return null;
}

export function Composer(props: ComposerProps) {
  const { pending, setPending, params, setParams, busy, engineUp, askEnabled, allowed, maxBytes } = props;
  const [text, setText] = useState("");
  const [showParams, setShowParams] = useState(false);
  const [showSamples, setShowSamples] = useState(false);
  const [paramError, setParamError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const samplesRef = useRef<HTMLDivElement>(null);
  const ids = useId();

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
    el.style.overflowY = el.scrollHeight > 220 ? "auto" : "hidden";
  }, [text, pending.length]);

  useEffect(() => {
    if (!showSamples) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !samplesRef.current?.contains(e.target as Node)) setShowSamples(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [showSamples]);

  const problem = problemsFor(pending, allowed, maxBytes);
  const hasFiles = pending.length > 0;
  const hasText = text.trim().length > 0;
  const canRun = hasFiles && engineUp && !problem && !paramError;
  const canAsk = !hasFiles && hasText && askEnabled === true;
  const canSend = !busy && (canRun || canAsk);

  const send = () => {
    if (!canSend) return;
    props.onSend(text);
    setText("");
    setShowParams(false);
  };

  const sendLabel = hasFiles ? `Run ${pending.length} file${pending.length === 1 ? "" : "s"}` : "Ask";
  const summary = paramSummary(params);
  const placeholder = hasFiles
    ? askEnabled
      ? "Optional: a question to ask once these are checked"
      : "Optional note"
    : props.hasDocs
      ? "Ask about the released documents, or attach more files"
      : "Attach files to check, or drop them anywhere here";

  let hint: string;
  if (!engineUp) hint = "The engine is not reachable, so files cannot be checked right now.";
  else if (problem) hint = problem;
  else if (hasFiles) hint = "Each file is checked on its own. Nothing is released unless its numbers tie out.";
  else if (askEnabled === false && (hasText || props.hasDocs)) hint = "Questions need ANTHROPIC_API_KEY on the web server. File checks still work.";
  else hint = askEnabled ? "Enter to send · Shift+Enter for a new line" : "Attach files to begin";

  return (
    <div className="ob-dock">
      <div className="composer">
        {showParams && (
          <ParamsPanel id={`${ids}-params`} params={params} setParams={setParams} onError={setParamError} modelAvailable={props.modelAvailable} modelIssue={props.modelIssue} />
        )}
        {hasFiles && (
          <ul className="chips composer-chips" aria-label="Files to check">
            {pending.map((p) => (
              <li key={p.id} className={`chip${p.file.size > maxBytes || (allowed.length && !allowed.includes(ext(p.file.name))) ? " chip--over" : ""}`}>
                <span className="chip-name">{p.file.name}</span>
                <span className="chip-size">{fmtBytes(p.file.size)}{p.params && paramSummary(p.params) ? ` · ${paramSummary(p.params)}` : ""}</span>
                <button type="button" className="icon-btn" aria-label={`Remove ${p.file.name}`} onClick={() => setPending((list) => list.filter((x) => x.id !== p.id))}>
                  <X size={13} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <label htmlFor={`${ids}-input`} className="sr-only">Message</label>
        <textarea
          id={`${ids}-input`}
          ref={area}
          className="composer-input"
          rows={1}
          value={text}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }}
          onPaste={(e) => {
            const files = Array.from(e.clipboardData.files);
            if (files.length) {
              e.preventDefault();
              props.onAddFiles(files);
            }
          }}
        />
        <div className="composer-bar">
          <div className="composer-tools">
            <input
              ref={fileInput}
              type="file"
              multiple
              hidden
              accept={allowed.join(",")}
              onChange={(e) => {
                props.onAddFiles(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
            />
            <button type="button" className="tool-btn" onClick={() => fileInput.current?.click()} disabled={busy}>
              <Paperclip size={15} /> Attach
            </button>
            <div ref={samplesRef} style={{ position: "relative" }}>
              <button
                type="button"
                className="tool-btn"
                aria-expanded={showSamples}
                aria-controls={`${ids}-samples`}
                onClick={() => setShowSamples((v) => !v)}
                disabled={!engineUp || props.samples.length === 0}
              >
                <FlaskConical size={15} /> Samples
              </button>
              {showSamples && (
                <div className="popover" id={`${ids}-samples`} role="menu" aria-label="Sample files">
                  <div className="popover-head mono-label">Synthetic golden set · {props.samples.length} files</div>
                  {props.samples.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      role="menuitem"
                      className="ob-sample"
                      onClick={() => {
                        props.onAddSample(s);
                        setShowSamples(false);
                      }}
                    >
                      <span>
                        <span className="ob-sample-name">{s.label}</span>
                        <span className="ob-sample-file">{s.filename}</span>
                      </span>
                      {s.expect_status === "ok" ? <span className="tag tag--ok">Releases</span> : <span className="tag tag--bad"><span className="dot" />{s.expect_code}</span>}
                      <span />
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              type="button"
              className="tool-btn"
              aria-expanded={showParams}
              aria-controls={`${ids}-params`}
              onClick={() => setShowParams((v) => !v)}
            >
              <SlidersHorizontal size={15} /> Params {summary && <span className="badge">{summary}</span>}
            </button>
          </div>
          {busy ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={props.onStop}>
              <Square size={13} /> Stop
            </button>
          ) : (
            <button type="button" className="btn btn-primary-landing btn-sm" onClick={send} disabled={!canSend}>
              {sendLabel} <ArrowUp size={15} />
            </button>
          )}
        </div>
      </div>
      <div className="composer-hint">
        <span className={`t-body-sm${problem || !engineUp ? " field-error" : ""}`} role={problem ? "alert" : undefined}>
          {(problem || !engineUp) && <span className="dot" aria-hidden="true" />}
          {hint}
        </span>
      </div>
    </div>
  );
}

const CUR = /^[A-Za-z]{3}$/;
const AMT = /^-?\d+(\.\d+)?$/;

function ParamsPanel({
  id,
  params,
  setParams,
  onError,
  modelAvailable,
  modelIssue,
}: {
  id: string;
  params: RunParams;
  setParams: (p: RunParams) => void;
  onError: (e: string | null) => void;
  modelAvailable: boolean;
  modelIssue?: string | null;
}) {
  const [cur, setCur] = useState(params.currency ?? "");
  const [open, setOpen] = useState(params.opening ?? "");
  const [acct, setAcct] = useState(params.account ?? "");
  const curBad = cur !== "" && !CUR.test(cur.trim());
  const openBad = open !== "" && !AMT.test(open.replace(/,/g, "").trim());

  useEffect(() => {
    onError(curBad ? "Currency must be three letters, like INR." : openBad ? "Opening balance must be a plain number, like 1000.00." : null);
    if (curBad || openBad) return;
    const next: RunParams = { ...params };
    if (cur.trim()) next.currency = cur.trim().toUpperCase();
    else delete next.currency;
    if (open.trim()) next.opening = open.replace(/,/g, "").trim();
    else delete next.opening;
    if (acct.trim()) next.account = acct.trim();
    else delete next.account;
    if (JSON.stringify(next) !== JSON.stringify(params)) setParams(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, open, acct, curBad, openBad]);

  return (
    <div className="params" id={id} role="group" aria-label="Run parameters">
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-cur`}>Currency</label>
        <input id={`${id}-cur`} className="field num" placeholder="From file" maxLength={3} value={cur} onChange={(e) => setCur(e.target.value)} aria-invalid={curBad} />
      </div>
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-open`}>Opening balance</label>
        <input id={`${id}-open`} className="field num" inputMode="decimal" placeholder="From file" value={open} onChange={(e) => setOpen(e.target.value)} aria-invalid={openBad} />
      </div>
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-acct`}>Account</label>
        <input id={`${id}-acct`} className="field" placeholder="Optional label" value={acct} onChange={(e) => setAcct(e.target.value)} />
      </div>
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-order`}>Date order</label>
        <select
          id={`${id}-order`}
          className="field"
          value={params.date_order ?? ""}
          onChange={(e) => {
            const v = e.target.value as "" | "dmy" | "mdy";
            const next = { ...params };
            if (v) next.date_order = v;
            else delete next.date_order;
            setParams(next);
          }}
        >
          <option value="">Prove from file</option>
          <option value="dmy">Day first (03/04 = 3 Apr)</option>
          <option value="mdy">Month first (03/04 = 4 Mar)</option>
        </select>
      </div>
      <div className="params-toggles">
        <label className="check">
          <input type="checkbox" checked={params.ocr !== false} onChange={(e) => setParams({ ...params, ocr: e.target.checked })} />
          Read scans with OCR
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={!!params.allow_derived_opening}
            onChange={(e) => setParams({ ...params, allow_derived_opening: e.target.checked || undefined })}
          />
          Allow derived opening balance
        </label>
        <label className="check" title={modelAvailable ? undefined : `Unavailable: ${modelIssue ?? "the engine has no usable model"}`}>
          <input type="checkbox" checked={!!params.model} disabled={!modelAvailable} onChange={(e) => setParams({ ...params, model: e.target.checked || undefined })} />
          Model cross-check for PDFs and scans
        </label>
      </div>
      <p className="params-help">
        Applies to every file in this run; sample files bring their own. A derived opening never counts as independent evidence.
        Dates are read in the order the file proves (a day above 12); bank statements without proof are read day-first, and
        PayPal and 1099-B refuse rather than guess. The model cross-check can only add refusals, never a release.
      </p>
    </div>
  );
}
