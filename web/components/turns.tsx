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
  busy,
  onRerun,
  onStop,
}: {
  turn: RunTurn;
  busy: boolean;
  onRerun: (run: RunTurn, index: number, p: RunParams) => void;
  onStop: () => void;
}) {
  const released = turn.files.filter((f) => f.doc?.status === "ok").length;
  const refused = turn.files.filter((f) => f.doc?.status === "refused").length;
  const pending = turn.files.length - released - refused;
  const done = turn.files.filter((f) => f.doc);
  const summary =
    turn.state === "running"
      ? `Checking ${turn.files.length} file${turn.files.length === 1 ? "" : "s"}${released + refused ? ` · ${released + refused} done` : ""}`
      : `${released} released · ${refused} refused${pending ? ` · ${pending} not finished` : ""}`;

  return (
    <section className="turn" aria-label="Run results">
      <div className="turn-agent-head">
        <Who label="Open Books" at={turn.at} />
        <span className="turn-agent-actions">
          <span className="mono-label" aria-live="polite">{summary}</span>
          {turn.state === "running" && (
            <button type="button" className="btn btn-ghost btn-xs" onClick={onStop}>
              <Square size={12} /> Stop
            </button>
          )}
          {turn.state !== "running" && done.length > 1 && (
            <button
              type="button"
              className="btn btn-ghost btn-xs"
              onClick={() => done.forEach((f, i) => setTimeout(() => downloadText(jsonFileName(f.name), docText(f.doc!)), i * 250))}
              title="Saves one JSON per file"
            >
              <Download size={14} /> Download all ({done.length})
            </button>
          )}
        </span>
      </div>
      {turn.error && <p className="error-line"><span className="dot" />{turn.error}</p>}
      {turn.files.map((f) => (
        <RunCard key={f.index} file={f} run={turn} busy={busy} onRerun={(i, p) => onRerun(turn, i, p)} />
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
