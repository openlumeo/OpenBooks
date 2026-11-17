"use client";

import { useId, useRef, useState, type KeyboardEvent } from "react";
import { Check, Copy, Download } from "lucide-react";
import { downloadText, fmtBytes, jsonFileName } from "@/lib/format";
import { fixesFor, REFUSAL_MEANING } from "@/lib/stages";
import { recallFile } from "@/lib/session-files";
import type { FileRun, RunParams, RunTurn } from "@/lib/types";
import { StageTrail } from "./stage-trail";
import { DataTab } from "./data-tab";
import { AssertionsTab } from "./assertions-tab";
import { EvidenceTab } from "./evidence-tab";
import { JsonTab, docText } from "./json-tab";
import { RefusalFix } from "./refusal-fix";

type Tab = "data" | "checks" | "evidence" | "json";
const TABS: { id: Tab; label: string }[] = [
  { id: "data", label: "Data" },
  { id: "checks", label: "Checks" },
  { id: "evidence", label: "Evidence" },
  { id: "json", label: "JSON" },
];

export function RunCard({
  file,
  run,
  busy,
  onRerun,
}: {
  file: FileRun;
  run: RunTurn;
  busy: boolean;
  onRerun: (index: number, p: RunParams) => void;
}) {
  const [tab, setTab] = useState<Tab>("data");
  const [record, setRecord] = useState("batch-1");
  const [copied, setCopied] = useState(false);
  const base = useId();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const doc = file.doc;

  const onTabKey = (e: KeyboardEvent, i: number) => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const n = (i + d + TABS.length) % TABS.length;
    setTab(TABS[n]!.id);
    tabRefs.current[n]?.focus();
  };

  const sha = doc?.status === "ok" ? doc.file.sha256 : doc?.status === "refused" ? doc.error.file_sha256 : null;

  return (
    <article className={`run-card${doc?.status === "refused" ? " run-card--refused" : ""}`} aria-label={`${file.name}: ${verdictWord(file)}`}>
      <header className="run-card-head">
        <h3 className="run-card-name">{file.name}</h3>
        <Verdict file={file} />
        <div className="run-card-meta">
          <span className="meta-item">{fmtBytes(file.size)}</span>
          {doc?.status === "ok" && (
            <>
              <span className="meta-item"><b>{doc.file.detected_format}</b></span>
              <span className="meta-item"><b>{doc.file.layout_version}</b></span>
              <span className="meta-item">method <b>{doc.file.method}</b></span>
              {doc.file.model && (
                <span
                  className="meta-item"
                  title={`Cross-checked by weights ${doc.file.model.weights_sha256} with calibration ${doc.file.model.calibration_sha256}`}
                >
                  model <b>{doc.file.model.weights_sha256.slice(0, 12)}</b>
                </span>
              )}
            </>
          )}
          {sha && (
            <button
              type="button"
              className="copy-inline"
              title={`sha256 ${sha} (copy)`}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(sha);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1400);
                } catch {
                  setCopied(false);
                }
              }}
            >
              sha256 {sha.slice(0, 12)} {copied ? <Check size={12} /> : <Copy size={12} />}
              <span className="sr-only">{copied ? "copied" : "copy full hash"}</span>
            </button>
          )}
        </div>
      </header>

      <StageTrail file={file} />

      <div className="run-card-body">
        {!doc && file.state !== "interrupted" && (
          <div aria-live="polite" className="panel">
            <span className="t-body-sm">{file.state === "queued" ? "Waiting for the files before it." : "Reading and checking this file."}</span>
            <div className="skeleton" style={{ width: "62%" }} />
            <div className="skeleton" style={{ width: "38%" }} />
          </div>
        )}

        {file.state === "interrupted" && (
          <p className="error-line"><span className="dot" />The run stopped before this file finished. Nothing was released for it.</p>
        )}

        {doc?.status === "refused" && (
          <div className="refusal">
            <p className="refusal-meaning">{REFUSAL_MEANING[doc.error.code]}</p>
            <p className="refusal-msg">{doc.error.message}</p>
            {fixesFor(doc.error.message).length > 0 && (
              <RefusalFix
                fields={fixesFor(doc.error.message)}
                available={!!recallFile(run.sourceTurnId, file.index)}
                disabled={busy}
                onRerun={(p) => onRerun(file.index, p)}
              />
            )}
          </div>
        )}

        {doc?.status === "ok" && (
          <>
            <p className="checks-line">
              <span><strong>{doc.assertions.filter((a) => a.passed).length} of {doc.assertions.length}</strong> checks tie out</span>
              <span>{doc.assertions.filter((a) => a.independent).length} independent of the parser</span>
              <span>{doc.data.transactions.length} rows</span>
            </p>
            <div role="tablist" aria-label={`${file.name} result`} className="tabs">
              {TABS.map((t, i) => (
                <button
                  key={t.id}
                  ref={(el) => {
                    tabRefs.current[i] = el;
                  }}
                  role="tab"
                  type="button"
                  id={`${base}-tab-${t.id}`}
                  aria-controls={`${base}-panel-${t.id}`}
                  aria-selected={tab === t.id}
                  tabIndex={tab === t.id ? 0 : -1}
                  className="tab"
                  onClick={() => setTab(t.id)}
                  onKeyDown={(e) => onTabKey(e, i)}
                >
                  {t.label}
                  {t.id === "checks" && <span className="tab-count">{doc.assertions.length}</span>}
                </button>
              ))}
            </div>
            <div role="tabpanel" id={`${base}-panel-${tab}`} aria-labelledby={`${base}-tab-${tab}`}>
              {tab === "data" && (
                <DataTab
                  doc={doc}
                  onPick={(id) => {
                    setRecord(id);
                    setTab("evidence");
                  }}
                />
              )}
              {tab === "checks" && <AssertionsTab assertions={doc.assertions} />}
              {tab === "evidence" && <EvidenceTab doc={doc} record={record} onRecord={setRecord} />}
              {tab === "json" && <JsonTab doc={doc} name={file.name} />}
            </div>
          </>
        )}

        {doc && (
          <div className="run-card-foot">
            <span className="mono-label">{doc.schema_version}</span>
            <button type="button" className="btn btn-ghost btn-xs" onClick={() => downloadText(jsonFileName(file.name), docText(doc))}>
              <Download size={14} /> {doc.status === "ok" ? "Download JSON" : "Download refusal"}
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

function verdictWord(f: FileRun): string {
  if (f.doc?.status === "ok") return "released";
  if (f.doc?.status === "refused") return `refused, ${f.doc.error.code}`;
  if (f.state === "interrupted") return "interrupted";
  return f.state === "queued" ? "queued" : "processing";
}

function Verdict({ file }: { file: FileRun }) {
  const doc = file.doc;
  if (doc?.status === "ok") {
    return (
      <span className="verdict verdict--ok">
        <Check size={13} strokeWidth={2.25} aria-hidden="true" /> Released
      </span>
    );
  }
  if (doc?.status === "refused") {
    return (
      <span className="verdict verdict--bad">
        <span className="dot" aria-hidden="true" /> Refused · {doc.error.code}
      </span>
    );
  }
  return (
    <span className="verdict verdict--pending">
      {file.state === "running" && <span className="dot dot--live" aria-hidden="true" />}
      {file.state === "interrupted" ? "Interrupted" : file.state === "queued" ? "Queued" : "Checking"}
    </span>
  );
}
