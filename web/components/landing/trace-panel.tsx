'use client';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ReconPanel } from './reconciliation';
import { TRACE_SAMPLE, type TraceEvidence } from './trace-data';
import styles from './trace.module.css';

const tx = TRACE_SAMPLE.transaction;

type TxField = { field: string; label: string; value: string; unit?: string; ev?: TraceEvidence };

function evidenceFor(field: string): TraceEvidence | undefined {
  return TRACE_SAMPLE.evidence.find((e) => e.key === `${tx.id}.${field}`);
}

const FIELDS: readonly TxField[] = [
  { field: 'date', label: 'Date', value: tx.date },
  { field: 'description', label: 'Description', value: tx.description ?? 'null' },
  { field: 'direction', label: 'Direction', value: tx.direction },
  { field: 'amount', label: 'Amount', value: tx.amount.amount, unit: tx.amount.currency },
  { field: 'balance_after', label: 'Balance after', value: tx.balance_after.amount, unit: tx.balance_after.currency },
].map((f) => ({ ...f, ev: evidenceFor(f.field) }));

const N = FIELDS.length;
const LINKED = FIELDS.filter((f) => f.ev).length;
const DWELL_EVIDENCE = 1500;
const DWELL_NONE = 950;
const DWELL_START = 900;

const show = (v: string | number | null | undefined): string => (v === null || v === undefined ? 'null' : String(v));
const fieldOf = (key: string): number => FIELDS.findIndex((f) => `${tx.id}.${f.field}` === key);

type LinkState = 'idle' | 'linked' | 'active';

/** Mock crop of the source page: the printed row, with the evidence bbox drawn at its real coordinates. */
function SourceCrop({ active }: { active: TxField | null }) {
  const shown = active?.ev?.bbox ? active : (FIELDS.find((f) => f.field === 'amount') as TxField);
  const [x1, y1, x2, y2] = shown?.ev?.bbox ?? [0, 0, 0, 0];
  const visible = Boolean(active?.ev?.bbox);
  const ink = (field: string) => (active?.field === field ? 'var(--text)' : 'var(--text-muted)');
  const ev = (field: string) => evidenceFor(field)?.bbox;
  const date = ev('date');
  const amt = ev('amount');
  const bal = ev('balance_after');
  return (
    <div className={styles.crop} aria-hidden="true">
      <div className={styles.cropHead}>
        <span>Source · {TRACE_SAMPLE.filename}</span>
        <span>
          {visible ? `page ${show(active?.ev?.page)} · bbox [${active?.ev?.bbox?.map((n) => +n.toFixed(1)).join(', ')}]` : 'page 1'}
        </span>
      </div>
      <svg viewBox="22 78 556 50" className={styles.cropSvg} preserveAspectRatio="xMidYMid meet" focusable="false">
        <g className={styles.cropFaint}>
          <text x="38" y="86" fontSize="6">DATE</text>
          <text x="140" y="86" fontSize="6">DESCRIPTION</text>
          <text x="424" y="86" fontSize="6">AMOUNT</text>
          <text x="512" y="86" fontSize="6">BALANCE</text>
          <rect x="30" y="91" width="535" height="0.5" />
        </g>
        <rect
          className={styles.bbox}
          style={{ x: x1 - 3, y: y1 - 1.5, width: x2 - x1 + 6, height: y2 - y1 + 3, opacity: visible ? 1 : 0 }}
        />
        {date ? (
          <text x={date[0]} y="107.4" fontSize="8" textLength={date[2] - date[0]} lengthAdjust="spacingAndGlyphs" fill={ink('date')}>
            {evidenceFor('date')?.raw_text}
          </text>
        ) : null}
        <text x="140" y="107.4" fontSize="8" fill={ink('description')}>
          {tx.description?.split(' ').slice(0, 4).join(' ')}
        </text>
        {amt ? (
          <text x={amt[0]} y="107.4" fontSize="8" textLength={amt[2] - amt[0]} lengthAdjust="spacingAndGlyphs" fill={ink('amount')}>
            {evidenceFor('amount')?.raw_text}
          </text>
        ) : null}
        {bal ? (
          <text x={bal[0]} y="107.4" fontSize="8" textLength={bal[2] - bal[0]} lengthAdjust="spacingAndGlyphs" fill={ink('balance_after')}>
            {evidenceFor('balance_after')?.raw_text}
          </text>
        ) : null}
      </svg>
    </div>
  );
}

export function TracePanel() {
  const [step, setStep] = useState<number>(N);
  const [motion, setMotion] = useState(false);
  const [inView, setInView] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const [link, setLink] = useState<{ d: string; key: string } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const evBlock = useRef<HTMLDivElement>(null);
  const hasConfidence = TRACE_SAMPLE.evidence.some((e) => e.confidence !== undefined);

  // No JS / reduced motion: the final, fully linked frame is the default.
  useLayoutEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: no-preference)');
    setMotion(mq.matches);
    if (mq.matches) setStep(-1);
    const onChange = () => {
      setMotion(mq.matches);
      if (!mq.matches) setStep(N);
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setInView(Boolean(e?.isIntersecting)), { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Timed sequence; pauses while offscreen.
  useEffect(() => {
    if (!motion || !inView || step >= N) return;
    const dwell = step < 0 ? DWELL_START : FIELDS[step]?.ev ? DWELL_EVIDENCE : DWELL_NONE;
    const id = window.setTimeout(() => setStep(step + 1), dwell);
    return () => window.clearTimeout(id);
  }, [motion, inView, step]);

  const sequenceActive = step >= 0 && step < N;
  const activeIdx = sequenceActive ? step : step >= N ? hover : null;
  const active = activeIdx !== null ? (FIELDS[activeIdx] ?? null) : null;
  const activeKey = active?.ev ? `${tx.id}.${active.field}` : null;

  // Connector from the highlighted field to its evidence row (two-column layout only).
  useLayoutEffect(() => {
    const g = grid.current;
    const eb = evBlock.current;
    if (!g || !eb || !activeKey || !active || !window.matchMedia('(min-width: 1400px)').matches) {
      setLink(null);
      return;
    }
    const f = g.querySelector<HTMLElement>(`[data-field="${active.field}"]`);
    const r = g.querySelector<HTMLElement>(`[data-ev="${activeKey}"]`);
    if (!f || !r) return;
    const gr = g.getBoundingClientRect();
    const fr = f.getBoundingClientRect();
    const rr = r.getBoundingClientRect();
    const er = eb.getBoundingClientRect();
    const x1 = fr.right - gr.left;
    const y1 = fr.top + fr.height / 2 - gr.top;
    const x2 = er.left - gr.left;
    const y2 = rr.top + rr.height / 2 - gr.top;
    const xm = x1 + (x2 - x1) / 2;
    setLink({ d: `M${x1} ${y1} H${xm} V${y2} H${x2}`, key: activeKey });
  }, [activeKey, active]);

  // Narrow layout: keep the active evidence row visible inside its scroll container.
  useEffect(() => {
    const eb = evBlock.current;
    if (!eb || !activeKey || window.matchMedia('(min-width: 1400px)').matches) return;
    const r = eb.querySelector<HTMLElement>(`[data-ev="${activeKey}"]`);
    if (!r) return;
    const left = r.offsetLeft;
    eb.scrollTo({ top: Math.max(0, r.offsetTop - 40), left, behavior: 'auto' });
  }, [activeKey]);

  const fieldState = (i: number): LinkState => {
    if (activeIdx === i) return 'active';
    return FIELDS[i]?.ev && (step >= N || i < step) ? 'linked' : 'idle';
  };

  let stepText: string;
  if (sequenceActive && active) {
    stepText = `Step ${step + 1}/${N} · ${active.label} → ${
      active.ev ? `page ${show(active.ev.page)} · row ${show(active.ev.row)} · ${active.ev.method}` : 'no evidence entry'
    }`;
  } else if (step >= N) {
    stepText = `${LINKED} of ${N} fields linked to source · ${N - LINKED} carry no evidence entry`;
  } else {
    stepText = 'Tracing each field to its source';
  }

  return (
    <div ref={root}>
      <ReconPanel title={`EVIDENCE · ${tx.id}`}>
        <div className={styles.stepbar}>
          <span className={styles.stepText} aria-hidden="true">
            {stepText}
          </span>
          <button
            type="button"
            className={styles.replay}
            onClick={() => setStep(0)}
            style={{ visibility: motion && step >= N ? 'visible' : 'hidden' }}
            tabIndex={motion && step >= N ? 0 : -1}
          >
            Replay trace
          </button>
        </div>
        <SourceCrop active={active} />
        <div className={styles.grid} ref={grid}>
          <section className={styles.txBlock} aria-label="Transaction as emitted">
            <dl className={styles.fields}>
              {FIELDS.map((f, i) => {
                const state = fieldState(i);
                return (
                  <div
                    key={f.field}
                    className={styles.field}
                    data-field={f.field}
                    data-state={state}
                    data-none={f.ev ? undefined : ''}
                    onMouseEnter={() => step >= N && setHover(i)}
                    onMouseLeave={() => setHover(null)}
                  >
                    <dt className={styles.label}>{f.label}</dt>
                    <dd className={styles.value}>
                      {f.value}
                      {f.unit ? <span className={styles.unit}>{f.unit}</span> : null}
                      <span className={styles.status}>
                        {f.ev
                          ? `${state === 'idle' ? '' : 'Linked · '}page ${show(f.ev.page)} · row ${show(f.ev.row)}`
                          : 'no evidence entry'}
                      </span>
                    </dd>
                  </div>
                );
              })}
            </dl>
            <p className={styles.meta}>
              {TRACE_SAMPLE.sampleId} · {TRACE_SAMPLE.layoutVersion} · {TRACE_SAMPLE.method}
            </p>
          </section>

          <div
            ref={evBlock}
            className={`lp-scroll lp-focusable ${styles.evBlock}`}
            role="region"
            aria-label="Evidence entries, scrollable"
            tabIndex={0}
          >
            <table className={styles.table}>
              <caption className={styles.caption}>Evidence entries for {tx.id}</caption>
              <thead>
                <tr>
                  <th scope="col">Key</th>
                  <th scope="col">Page</th>
                  <th scope="col">Bbox</th>
                  <th scope="col">Row</th>
                  <th scope="col">Raw text</th>
                  <th scope="col">Method</th>
                  {hasConfidence ? <th scope="col">Confidence</th> : null}
                </tr>
              </thead>
              <tbody>
                {TRACE_SAMPLE.evidence.map((e) => {
                  const idx = fieldOf(e.key);
                  const state = idx >= 0 ? fieldState(idx) : 'idle';
                  return (
                    <tr key={e.key} data-ev={e.key} data-state={state}>
                      <th scope="row" className={styles.key}>
                        {e.key}
                      </th>
                      <td>{show(e.page)}</td>
                      <td className={styles.bboxCell}>{e.bbox ? `[${e.bbox.map((n) => +n.toFixed(1)).join(', ')}]` : 'null'}</td>
                      <td>{show(e.row)}</td>
                      <td className={styles.raw}>{e.raw_text}</td>
                      <td>{e.method}</td>
                      {hasConfidence ? <td>{show(e.confidence)}</td> : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {link ? (
            <svg className={styles.linkSvg} aria-hidden="true" focusable="false">
              <path key={link.key} d={link.d} pathLength={1} className={styles.linkPath} />
            </svg>
          ) : null}
        </div>
      </ReconPanel>
    </div>
  );
}
