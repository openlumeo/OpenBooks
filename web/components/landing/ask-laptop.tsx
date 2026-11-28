"use client";

import { ArrowUp, Check, FileSpreadsheet, FileText, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DeviceFrame } from "./device-frame";
import { ASK_EXAMPLE, ASK_FOLLOW_UP } from "./ask-data";
import styles from "./ask-laptop.module.css";

type Token = { kind: "text" | "fig" | "cite"; v: string };
type Call = { direction: "debit" | "credit"; count: number; sum: string };
type Turn = { q: string; calls: Call[]; tokens: Token[]; plain: string };

const { debit, credit, file, currency, batchId } = ASK_EXAMPLE;

function words(tokens: Token[]): Token[] {
  const out: Token[] = [];
  for (const t of tokens) {
    if (t.kind !== "text") out.push(t);
    else for (const w of t.v.match(/\S+\s*|\s+/g) ?? []) out.push({ kind: "text", v: w });
  }
  return out;
}

function plainOf(tokens: Token[]): string {
  return tokens.map((t) => t.v).join("");
}

const A1: Token[] = [
  { kind: "fig", v: `${debit.sum} ${currency}` },
  { kind: "text", v: " went out on one debit: record " },
  { kind: "cite", v: debit.ids[0] },
  { kind: "text", v: " in " },
  { kind: "cite", v: file },
  { kind: "text", v: ` (${debit.date}, ${debit.description}). ` },
  { kind: "fig", v: `${credit.sum} ${currency}` },
  { kind: "text", v: " came in on one credit: record " },
  { kind: "cite", v: credit.ids[0] },
  { kind: "text", v: " in " },
  { kind: "cite", v: file },
  { kind: "text", v: ` (${credit.date}, ${credit.description}).` },
];

const A2: Token[] = [
  { kind: "text", v: "One credit: record " },
  { kind: "cite", v: credit.ids[0] },
  { kind: "text", v: " in " },
  { kind: "cite", v: file },
  { kind: "text", v: ", " },
  { kind: "fig", v: `${credit.sum} ${currency}` },
  { kind: "text", v: "." },
];

const call = (direction: "debit" | "credit"): Call => ({
  direction,
  count: ASK_EXAMPLE[direction].count,
  sum: ASK_EXAMPLE[direction].sum,
});

const TURNS: Turn[] = [
  { q: ASK_EXAMPLE.question, calls: [call("debit"), call("credit")], tokens: words(A1), plain: plainOf(A1) },
  { q: ASK_FOLLOW_UP.question, calls: [call("credit")], tokens: words(A2), plain: plainOf(A2) },
];

type TurnState = { toolsShown: number; toolsDone: number; words: number; cite: boolean };
type View = { inp: string; turns: TurnState[] };

const EMPTY: View = { inp: "", turns: [] };
const FINAL: View = {
  inp: "",
  turns: TURNS.map((t) => ({ toolsShown: t.calls.length, toolsDone: t.calls.length, words: t.tokens.length, cite: true })),
};

const rowsLabel = (n: number) => `${n} ${n === 1 ? "row" : "rows"}`;
const callText = (c: Call) => `QUERY · direction=${c.direction} → ${rowsLabel(c.count)}, ${c.sum} ${currency}`;

function Answer({ turn, count }: { turn: Turn; count: number }) {
  return (
    <p className={styles.answer}>
      {turn.tokens.slice(0, count).map((t, i) =>
        t.kind === "fig" ? (
          <span key={i} className={styles.figure}>
            {t.v}
          </span>
        ) : t.kind === "cite" ? (
          <code key={i} className={styles.cite}>
            {t.v}
          </code>
        ) : (
          <span key={i}>{t.v}</span>
        ),
      )}
    </p>
  );
}

export function AskLaptop() {
  const [animated, setAnimated] = useState(false);
  const [view, setView] = useState<View>(FINAL);
  const [typing, setTyping] = useState(false);
  const [runId, setRunId] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);
  const ratio = useRef(0);
  const onScreen = useRef(false);
  const started = useRef(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setAnimated(true);
    setView(EMPTY);
  }, []);

  useEffect(() => {
    const el = rootRef.current;
    if (!animated || !el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (!e) return;
        ratio.current = e.intersectionRatio;
        onScreen.current = e.intersectionRatio > 0.15;
        if (e.intersectionRatio >= 0.5) started.current = true;
      },
      { threshold: [0, 0.15, 0.5, 0.75, 1] },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [animated]);

  useEffect(() => {
    if (!animated) return;
    let dead = false;

    // Counts down only while the demo is on screen; resolves immediately false if cancelled.
    const wait = async (ms: number, gateOnStart = false) => {
      let left = ms;
      while (!dead) {
        if (gateOnStart ? started.current : onScreen.current) {
          if (left <= 0) return;
          const step = Math.min(40, left);
          await new Promise((r) => setTimeout(r, step));
          left -= step;
        } else {
          await new Promise((r) => setTimeout(r, 80));
        }
      }
    };
    const patch = (i: number, p: Partial<TurnState>) =>
      setView((v) => ({ ...v, turns: v.turns.map((t, j) => (j === i ? { ...t, ...p } : t)) }));

    (async () => {
      setView(EMPTY);
      await wait(0, true);
      for (let i = 0; i < TURNS.length && !dead; i++) {
        const turn = TURNS[i]!;
        await wait(i === 0 ? 700 : 1500);
        setTyping(true);
        for (let c = 1; c <= turn.q.length && !dead; c++) {
          setView((v) => ({ ...v, inp: turn.q.slice(0, c) }));
          const ch = turn.q[c - 1];
          await wait(35 + Math.random() * 25 + (ch === " " ? 25 : 0));
        }
        await wait(450);
        if (dead) return;
        setTyping(false);
        setView((v) => ({
          inp: "",
          turns: [...v.turns, { toolsShown: 0, toolsDone: 0, words: 0, cite: false }],
        }));
        await wait(350);
        for (let k = 0; k < turn.calls.length && !dead; k++) {
          patch(i, { toolsShown: k + 1 });
          await wait(750);
          patch(i, { toolsDone: k + 1 });
          await wait(180);
        }
        await wait(300);
        for (let w = 1; w <= turn.tokens.length && !dead; w++) {
          patch(i, { words: w });
          await wait(turn.tokens[w - 1]!.kind === "text" ? 55 : 110);
        }
        await wait(250);
        patch(i, { cite: true });
      }
      await wait(9000);
      if (!dead) setRunId((n) => n + 1);
    })();

    return () => {
      dead = true;
    };
  }, [animated, runId]);

  useEffect(() => {
    const el = chatRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [view]);

  const live = animated;
  const running = live && (typing || view.turns.length === 0 || view.inp.length > 0);
  const transcript = TURNS.map((t) => `${t.q} ${t.calls.map(callText).join(". ")}. ${t.plain} Computed in code over ${batchId}.`).join(" ");

  return (
    <div ref={rootRef} className={styles.root}>
      <DeviceFrame variant="laptop">
        <div className={styles.desktop} aria-hidden="true">
          <div className={styles.menubar}>
            <span className={styles.glyph} />
            <span className={styles.appName}>Open Books</span>
            <span className={styles.menu}>File</span>
            <span className={styles.menu}>Edit</span>
            <span className={styles.menu}>View</span>
            <span className={styles.menu}>Window</span>
            <span className={styles.spacer} />
            <span className={styles.clock}>Sat 9:41</span>
          </div>
          <div className={styles.window}>
            <div className={styles.titlebar}>
              <span className={styles.lights}>
                <i />
                <i />
                <i />
              </span>
              <span className={styles.title}>Open Books — Ask</span>
              <span className={styles.titleFile}>{file}</span>
            </div>
            <div ref={chatRef} className={styles.chat}>
              <div className={styles.thread}>
                {view.turns.map((ts, i) => {
                  const turn = TURNS[i]!;
                  const answering = ts.words > 0;
                  return (
                    <div key={i} className={styles.exchange}>
                      <p className={styles.bubble}>{turn.q}</p>
                      {ts.toolsShown > 0 ? (
                        <div className={styles.tools}>
                          <span className={styles.label}>
                            {ts.toolsDone < turn.calls.length ? "Running query" : "Tool calls"}
                          </span>
                          {turn.calls.slice(0, ts.toolsShown).map((c, k) => {
                            const done = k < ts.toolsDone;
                            return (
                              <div key={k} className={styles.tool}>
                                <span className={styles.status}>
                                  {done ? (
                                    <Check size={12} strokeWidth={2.25} className={styles.tick} />
                                  ) : (
                                    <span className={styles.spinner} />
                                  )}
                                </span>
                                <span>{callText(c)}</span>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                      {answering ? (
                        <div className={styles.reply}>
                          <Answer turn={turn} count={ts.words} />
                          {ts.cite ? (
                            <p className={styles.citation}>
                              <Check size={12} strokeWidth={2.25} />
                              Computed in code · {batchId}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
            <div className={styles.composer}>
              <div className={styles.input}>
                {view.inp ? (
                  <span className={styles.typed}>{view.inp}</span>
                ) : (
                  <span className={styles.placeholder}>Ask about {file}</span>
                )}
                {live && running ? <span className={`${styles.caret} ${typing ? styles.caretSolid : ""}`} /> : null}
              </div>
              <span className={styles.send}>
                <ArrowUp size={14} strokeWidth={2} />
              </span>
            </div>
          </div>
          <div className={styles.icons}>
            <span className={styles.icon}>
              <span className={styles.iconGlyph}>
                <FileText size={18} strokeWidth={1.6} />
              </span>
              <span className={styles.iconLabel}>statement.csv</span>
            </span>
            <span className={styles.icon}>
              <span className={styles.iconGlyph}>
                <FileSpreadsheet size={18} strokeWidth={1.6} />
              </span>
              <span className={styles.iconLabel}>razorpay.csv</span>
            </span>
          </div>
        </div>
      </DeviceFrame>
      <p className={styles.sr}>{transcript}</p>
      {live ? (
        <button type="button" className={styles.replay} onClick={() => setRunId((n) => n + 1)}>
          <RotateCcw size={13} strokeWidth={1.75} aria-hidden="true" />
          Replay
        </button>
      ) : null}
    </div>
  );
}
