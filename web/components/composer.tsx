"use client";

import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { ArrowUp, Paperclip, SlidersHorizontal, Square, X } from "lucide-react";
import { fmtBytes, paramSummary } from "@/lib/format";
import type { RunParams, Sample } from "@/lib/types";
import type { Workspace } from "@/lib/use-workspace";
import { ParamsPanel } from "./composer-parts/params-panel";
import { SamplesMenu } from "./composer-parts/samples-menu";
import {
  composerHint,
  isImageName,
  isOverLimit,
  problemsFor,
  type Pending,
} from "./composer-parts/problems";

export type { Pending } from "./composer-parts/problems";

const TEXTAREA_MAX_PX = 220;

type ComposerProps = {
  pending: Pending[];
  setPending: (fn: (p: Pending[]) => Pending[]) => void;
  params: RunParams;
  setParams: (p: RunParams) => void;
  samples: Sample[];
  onAddSample: (s: Sample) => void;
  onAddFiles: (files: File[]) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  operation: Workspace["operation"];
  locked: boolean;
  attachInput: RefObject<HTMLInputElement | null>;
  engineUp: boolean;
  askEnabled: boolean | null;
  allowed: string[];
  maxBytes: number;
  modelAvailable: boolean;
  ocrIssue?: string | null;
  modelIssue?: string | null;
  hasDocs: boolean;
};

export function Composer(props: ComposerProps) {
  const { pending, setPending, params, setParams, operation, locked, engineUp, askEnabled, allowed, maxBytes } = props;
  const [text, setText] = useState("");
  const [showParams, setShowParams] = useState(false);
  const [paramError, setParamError] = useState<string | null>(null);
  const fileInput = props.attachInput;
  const area = useRef<HTMLTextAreaElement>(null);
  const ids = useId();

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, TEXTAREA_MAX_PX)}px`;
    el.style.overflowY = el.scrollHeight > TEXTAREA_MAX_PX ? "auto" : "hidden";
  }, [text, pending.length]);

  const problem = problemsFor(pending, allowed, maxBytes);
  const hasFiles = pending.length > 0;
  const hasText = text.trim().length > 0;
  const canRun = hasFiles && engineUp && !problem && !paramError;
  const canAsk = !hasFiles && hasText && askEnabled === true;
  const canSend = !locked && (canRun || canAsk);

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
  const hint = composerHint({
    operation, engineUp, problem, hasFiles, hasText, hasDocs: props.hasDocs, askEnabled,
    ocrIssue: props.ocrIssue, hasImage: pending.some(({ file }) => isImageName(file.name)),
  });

  return (
    <div className="ob-dock">
      <div className="composer">
        {showParams && (
          <ParamsPanel id={`${ids}-params`} params={params} setParams={setParams} onError={setParamError} modelAvailable={props.modelAvailable} modelIssue={props.modelIssue} />
        )}
        {hasFiles && (
          <ul className="chips composer-chips" aria-label="Files to check">
            {pending.map((p) => {
              const over = isOverLimit(p, allowed, maxBytes);
              const summaryText = p.params ? paramSummary(p.params) : "";
              return (
                <li key={p.id} className={`chip${over ? " chip--over" : ""}`}>
                  <svg className="chip-icon" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
                    <path d="M4.2 1.6 C6.5 1.4 8 1.5 9.6 1.7 L12.8 5.1 C12.9 8 12.7 11 12.9 14.6 C10 14.8 7 14.5 4 14.6 C4.1 11 4 5 4.2 1.6 Z" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
                    <path d="M9.6 1.7 C9.5 3.2 9.6 4.2 9.7 5.1 L12.8 5.1" fill="none" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
                  </svg>
                  <span className="chip-name">{p.file.name}</span>
                  <span className="chip-size">{fmtBytes(p.file.size)}{summaryText ? ` · ${summaryText}` : ""}</span>
                  <button type="button" className="icon-btn" aria-label={`Remove ${p.file.name}`} onClick={() => setPending((list) => list.filter((x) => x.id !== p.id))}>
                    <X size={13} />
                  </button>
                </li>
              );
            })}
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
            <button type="button" className="tool-btn" onClick={() => fileInput.current?.click()} disabled={locked}>
              <Paperclip size={15} /> Attach
            </button>
            <SamplesMenu
              samples={props.samples}
              disabled={locked || !engineUp || props.samples.length === 0}
              onAddSample={props.onAddSample}
            />
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
          {operation && operation !== "history" ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={props.onStop}>
              <Square size={13} /> Stop
            </button>
          ) : (
            <button type="button" className="btn btn-primary-landing btn-sm" onClick={send} disabled={!canSend} aria-busy={locked || undefined}>
              {sendLabel} <ArrowUp size={15} />
            </button>
          )}
        </div>
      </div>
      <div className="composer-hint">
        <span className={`t-body-sm${problem || !engineUp ? " field-error" : ""}`} role={problem ? "alert" : "status"}>
          {(problem || !engineUp) && <span className="dot" aria-hidden="true" />}
          {hint}
        </span>
      </div>
    </div>
  );
}
