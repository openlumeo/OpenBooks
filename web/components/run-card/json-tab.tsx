"use client";

import { useState } from "react";
import { Check, Copy, Download } from "lucide-react";
import { downloadText, jsonFileName } from "@/lib/format";
import type { EngineDoc } from "@/lib/types";

export function docText(doc: EngineDoc): string {
  return JSON.stringify(doc, null, 2) + "\n";
}

export function JsonTab({ doc, name }: { doc: EngineDoc; name: string }) {
  const [copied, setCopied] = useState(false);
  const text = docText(doc);
  return (
    <div className="panel">
      <div className="panel-actions">
        <button
          type="button"
          className="btn btn-ghost btn-xs"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 1600);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy JSON"}
        </button>
        <button type="button" className="btn btn-ghost btn-xs" onClick={() => downloadText(jsonFileName(name), text)}>
          <Download size={14} /> Download {jsonFileName(name)}
        </button>
      </div>
      <pre className="json" tabIndex={0} aria-label="openbooks.v1 JSON">{text}</pre>
    </div>
  );
}
