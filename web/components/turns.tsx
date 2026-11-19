"use client";

import { ArrowRight, Download, Split, Square } from "lucide-react";
import { LumeoMark } from "@/components/brand/lumeo-mark";
import { RunCard } from "@/components/run-card/run-card";
import { docText } from "@/components/run-card/json-tab";
import { downloadText, fmtBytes, fmtTime, jsonFileName, paramSummary } from "@/lib/format";
import { groupAmount } from "@/lib/ledger";
import { Markdown } from "@/lib/markdown";
import type { AnswerTurn, LinksTurn, RunParams, RunTurn, UserAskTurn, UserRunTurn } from "@/lib/types";

function Who({ label, at }: { label: string; at: number }) {
  return (
    <span className="turn-agent-who">
      <LumeoMark size={18} />
      <span className="mono-label">{label} · {fmtTime(at)}</span>
    </span>
  );
}

export function UserRun({ turn }: { turn: UserRunTurn }) {
  const p = paramSummary(turn.params);
  return (
    <div className="turn turn-user">
      <div className="turn-user-body">
        {turn.note && <p className="turn-user-text">{turn.note}</p>}
        <ul className="chips" aria-label="Files">
          {turn.files.map((f, i) => (
            <li key={i} className="chip">
              <span className="chip-name">{f.name}</span>
              <span className="chip-size">{fmtBytes(f.size)}</span>
            </li>
          ))}
        </ul>
        {p && <span className="param-line">{p}</span>}
      </div>
    </div>
  );
}

export function UserAsk({ turn }: { turn: UserAskTurn }) {
  return (
    <div className="turn turn-user">
      <div className="turn-user-body">
        <p className="turn-user-text">{turn.text}</p>
      </div>
    </div>
  );
}

export function RunView({
  turn,
  recoveryDisabled,
  onRerun,
  onStop,
  onAttach,
}: {
  turn: RunTurn;
  recoveryDisabled: boolean;
  onRerun: (run: RunTurn, index: number, p: RunParams) => void;
  onStop: () => void;
  onAttach: () => void;
}) {
  const released = turn.files.filter((f) => f.doc?.status === "ok");
  const refused = turn.files.filter((f) => f.doc?.status === "refused");
  const interrupted = turn.files.filter((f) => f.state === "interrupted");
  const waiting = turn.files.length - released.length - refused.length - interrupted.length;
  const done = turn.files.filter((f) => f.doc);
  const headingId = `review-${turn.id}`;
  const fileId = (index: number) => `${headingId}-file-${index}`;

  return (
    <section className="turn" aria-labelledby={headingId}>
      <div className="turn-agent-head">
        <Who label="Open Books" at={turn.at} />
      </div>
      <div className="batch-review">
        <div className="batch-review-head">
          <div>
            <h2 id={headingId}>Batch review</h2>
            <p className="mono-label">{turn.files.length} {turn.files.length === 1 ? "file" : "files"}{waiting ? ` · ${waiting} awaiting results` : ""}</p>
          </div>
          {turn.state === "running" && (
            <button type="button" className="btn btn-ghost btn-xs" onClick={onStop}>
              <Square size={12} /> Stop
            </button>
          )}
          {turn.state !== "running" && done.length > 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-xs batch-export"
              onClick={() => done.forEach((f, i) => setTimeout(() => downloadText(jsonFileName(f.name), docText(f.doc!)), i * 250))}
              title="Saves one JSON per file"
            >
              <Download size={14} /> Export JSON ({done.length})
            </button>
          )}
        </div>
        <dl className="batch-metrics">
          {([
            { label: "Released", tone: "released", files: released, action: "Review checks" },
            { label: "Refused", tone: "refused", files: refused, action: "Review refusal" },
            { label: "Interrupted", tone: "interrupted", files: interrupted, action: "Recover file" },
          ] as const).map(({ label, tone, files, action }) => (
            <div className={`batch-metric batch-metric--${tone}`} key={label}>
              <dt>{label}</dt>
              <dd className="batch-metric-count num">{files.length}</dd>
              {files[0] && <dd><a href={`#${fileId(files[0].index)}`}>{action}<ArrowRight size={12} aria-hidden="true" /></a></dd>}
            </div>
          ))}
        </dl>
        <span className="sr-only" role="status">
          {released.length} released, {refused.length} refused, {interrupted.length} interrupted, {waiting} awaiting results.
        </span>
      </div>
      {turn.error && <p className="error-line"><span className="dot" />{turn.error}</p>}
      {turn.linkError && <p className="error-line"><span className="dot" />{turn.linkError}</p>}
      {turn.files.map((f) => (
        <RunCard key={f.index} id={fileId(f.index)} file={f} run={turn} recoveryDisabled={recoveryDisabled} onRerun={(i, p) => onRerun(turn, i, p)} onAttach={onAttach} />
      ))}
    </section>
  );
}

export function AnswerView({ turn, onStop }: { turn: AnswerTurn; onStop: () => void }) {
  return (
    <section className="turn" aria-label="Answer">
      <div className="turn-agent-head">
        <Who label="Open Books" at={turn.at} />
        {turn.state === "streaming" && (
          <button type="button" className="btn btn-ghost btn-xs" onClick={onStop}>
            <Square size={12} /> Stop
          </button>
        )}
      </div>
      <div className="answer">
        {turn.tools.length > 0 && (
          <ul className="tools" aria-label="Lookups computed by Open Books">
            {turn.tools.map((t, i) => (
              <li key={i} className="tool-line">
                <b>{t.name === "query_transactions" ? "Query" : "Evidence"}</b>
                {t.summary}
              </li>
            ))}
          </ul>
        )}
        <div className="answer-text" aria-live={turn.state === "streaming" ? "polite" : undefined} aria-busy={turn.state === "streaming"}>
          {turn.text ? <Markdown text={turn.text} /> : turn.state === "streaming" ? <span className="t-body-sm">Reading the documents…</span> : null}
          {turn.state === "streaming" && turn.text && <span className="caret" aria-hidden="true" />}
        </div>
        {turn.error && <p className="error-line"><span className="dot" />{turn.error}</p>}
      </div>
    </section>
  );
}

function endLabel(id: string, names: Record<string, string>): { file: string; rec: string } {
  const [sha = "", ...rest] = id.split(":");
  return { file: names[sha] ?? sha, rec: rest.join(" · ") };
}

export function LinksView({ turn }: { turn: LinksTurn }) {
  const { report, names } = turn;
  return (
    <section className="turn" aria-label="Links across files">
      <div className="turn-agent-head">
        <Who label="Open Books · links" at={turn.at} />
        <span className="mono-label">{report.links.length} linked · {report.ambiguous.length} ambiguous · {report.unlinked_sources.length} unlinked</span>
      </div>
      <div className="links">
        <div className="links-head">
          <span className="t-body-sm">
            Payouts and remittances matched to the bank credit that received them. Amounts must be exactly equal and the date inside
            the window. Ties are reported, never resolved by guessing.
          </span>
        </div>
        {report.links.map((l) => {
          const c = endLabel(l.credit, names);
          return (
            <div className="link-row" key={l.id}>
              <span className="link-end">
                {l.sources.map((s) => {
                  const e = endLabel(s, names);
                  return (
                    <span key={s}>
                      <b>{e.file}</b>
                      {e.rec}
                    </span>
                  );
                })}
              </span>
              <span className="link-arrow"><ArrowRight size={15} aria-hidden="true" /><span className="sr-only">paid into</span></span>
              <span className="link-end">
                <b>{c.file}</b>
                {c.rec}
              </span>
              <span className="num">{groupAmount(l.amount.amount, l.amount.currency)} {l.amount.currency}</span>
            </div>
          );
        })}
        {report.ambiguous.map((a, i) => {
          const c = endLabel(a.credit, names);
          return (
            <div className="link-row link-row--ambiguous" key={`amb-${i}`}>
              <span className="link-end">
                <b>{a.source ? endLabel(a.source, names).file : `${a.sources?.length ?? 0} possible groups`}</b>
                {a.source ? endLabel(a.source, names).rec : ""}
              </span>
              <span className="link-arrow"><Split size={15} aria-hidden="true" /><span className="sr-only">could be either of</span></span>
              <span className="link-end">
                <b>{c.file}</b>
                {c.rec}
              </span>
              <span className="tag tag--bad"><span className="dot" />Ambiguous</span>
            </div>
          );
        })}
        {report.links.length === 0 && report.ambiguous.length === 0 && (
          <div className="link-row"><span className="t-body-sm">No payout or remittance matched a bank credit exactly.</span></div>
        )}
      </div>
    </section>
  );
}
