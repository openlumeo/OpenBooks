"use client";

import { ArrowUpRight, FileCheck2, FlaskConical, Paperclip } from "lucide-react";
import { fmtBytes } from "@/lib/format";
import { MAX_TEXT_FILE_BYTES } from "@/lib/guards";
import type { Formats } from "@/lib/types";
import { MAX_FILES } from "./composer-parts/problems";

export function EmptyState({ formats, onAttach, disabled, onSample }: {
  formats: Formats | null;
  onAttach: () => void;
  disabled: boolean;
  onSample?: () => void;
}) {
  return (
    <div className="ob-empty">
      <div className="ob-empty-head">
        <FileCheck2 className="ob-empty-icon" size={34} aria-hidden="true" />
        <h1 className="t-display t-h2">What would you like to verify?</h1>
        <p>Attach a statement, settlement, tax document, or workpaper to check its numbers.</p>
        <button type="button" className="btn btn-primary-landing btn-sm" onClick={onAttach} disabled={disabled}>
          <Paperclip size={15} aria-hidden="true" /> Attach files
        </button>
        <div className="ob-empty-links">
          {onSample && <button type="button" className="tool-btn" onClick={onSample} disabled={disabled}>
            <FlaskConical size={14} aria-hidden="true" /> Try a sample
          </button>}
          <a href="/get-started">Connect an AI agent <ArrowUpRight size={13} aria-hidden="true" /></a>
          <a href="/docs">Documentation</a>
        </div>
        {formats && (
          <details className="ob-empty-formats">
            <summary>Supported files and limits</summary>
            <p>{formats.allowed_extensions.join(", ")}</p>
            <p>
              Up to {MAX_FILES} files and {fmtBytes(formats.max_bytes)} per run.
              Text files may be up to {fmtBytes(Math.min(MAX_TEXT_FILE_BYTES, formats.max_bytes))} each.
            </p>
          </details>
        )}
      </div>
    </div>
  );
}
