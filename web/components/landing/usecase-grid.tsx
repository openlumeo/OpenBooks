"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { STAGES } from "@/lib/stages";
import { USE_CASES, type UseCase } from "./usecase-data";
import styles from "./usecase-grid.module.css";

const CLOSE_GRACE_MS = 220;
const FINAL = 5;
/** ms spent on each step: chip enters, four stages, then the outcome holds. */
const STEP_MS = [550, 650, 650, 650, 650, 3800];

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return reduced;
}

function Pipeline({ item }: { item: UseCase }) {
  const reduced = useReducedMotion();
  const [step, setStep] = useState(0);
  const s = reduced ? FINAL : step;
  const refused = item.result.kind === "refused";
  const failIdx = refused ? 3 : -1;

  useEffect(() => {
    if (reduced) return;
    const id = window.setTimeout(() => setStep((v) => (v >= FINAL ? 0 : v + 1)), STEP_MS[step]);
    return () => window.clearTimeout(id);
  }, [step, reduced]);

  return (
    <div className={styles.pipe} data-step={s}>
      <p className={styles.chip} data-on={s >= 0 ? "" : undefined}>
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className={styles.chipGlyph}>
          <path d="M7 4h7l4 4v12H7zM14 4v4h4" />
        </svg>
        <span>{item.file}</span>
      </p>

      <ol className={styles.stages} aria-hidden="true">
        {STAGES.map((st, i) => {
          const state =
            s > i + 1 ? (i === failIdx ? "failed" : "passed") : s === i + 1 ? "active" : "pending";
          return (
            <li key={st.id} className={styles.stage} data-state={state}>
              <span className={styles.node} />
              <span className={styles.stageLabel}>{st.label}</span>
              <span className={styles.caption}>
                {state === "active" ? "Checking" : state === "pending" ? "" : item.captions[i]}
              </span>
            </li>
          );
        })}
      </ol>

      <div className={styles.outcome} data-show={s === FINAL ? "" : undefined} data-kind={item.result.kind} role="status">
        {s === FINAL && item.result.kind === "released" ? (
          <>
            <p className={styles.stamp}>Released</p>
            <pre className={styles.json}>
              {item.result.json.map((l) => (
                <span key={l}>{l}</span>
              ))}
            </pre>
          </>
        ) : null}
        {s === FINAL && item.result.kind === "refused" ? (
          <>
            <p className={styles.refCode}>{item.result.code}</p>
            <p className={styles.refWhy}>{item.result.meaning}</p>
            <p className={styles.refOut}>No output released.</p>
          </>
        ) : null}
      </div>
    </div>
  );
}

type Place = { x: number; above: boolean };

function Tile({
  item,
  open,
  onOpen,
  onLeave,
  onCancelLeave,
}: {
  item: UseCase;
  open: boolean;
  onOpen: (id: string) => void;
  onLeave: (id: string) => void;
  onCancelLeave: () => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const popId = useId();

  useLayoutEffect(() => {
    if (!open) {
      setPlace(null);
      return;
    }
    const w = wrap.current;
    const p = pop.current;
    if (!w || !p) return;
    const r = w.getBoundingClientRect();
    const vw = document.documentElement.clientWidth;
    const vh = window.innerHeight;
    const pw = p.offsetWidth;
    const ph = p.offsetHeight;
    const margin = 12;
    let x = 0;
    if (r.left + x + pw > vw - margin) x = vw - margin - pw - r.left;
    if (r.left + x < margin) x = margin - r.left;
    const below = vh - r.bottom;
    const above = r.top;
    setPlace({ x, above: below < ph + 16 && above >= ph + 16 + 72 });
  }, [open]);

  return (
    <div
      ref={wrap}
      className={styles.tile}
      data-uc-tile={item.id}
      data-open={open ? "" : undefined}
      style={{ "--span": item.span } as CSSProperties}
      onPointerEnter={(e) => {
        if (e.pointerType === "mouse") {
          onCancelLeave();
          onOpen(item.id);
        }
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === "mouse") onLeave(item.id);
      }}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onLeave(item.id);
      }}
    >
      <button
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        onFocus={() => {
          onCancelLeave();
          onOpen(item.id);
        }}
        onClick={() => {
          onCancelLeave();
          onOpen(item.id);
        }}
      >
        <span className={styles.title}>{item.title}</span>
        <span className={styles.outcomeText}>{item.outcome}</span>
        <span className={styles.io}>{item.io}</span>
        <span className={styles.foot}>
          <span className={styles.via}>
            {item.via.map((v) => (
              <span key={v} className={styles.viaItem}>
                {v}
              </span>
            ))}
          </span>
          <span className={styles.hint}>
            <span className={styles.hintHover}>Hover to run</span>
            <span className={styles.hintTouch}>Tap to run</span>
          </span>
        </span>
      </button>

      {open ? (
        <div
          ref={pop}
          id={popId}
          className={styles.pop}
          role="group"
          aria-label={`${item.title}: pipeline`}
          data-above={place?.above ? "" : undefined}
          data-ready={place ? "" : undefined}
          style={{ "--pop-x": `${place?.x ?? 0}px` } as CSSProperties}
        >
          <Pipeline item={item} />
        </div>
      ) : null}
    </div>
  );
}

export function UseCaseGrid() {
  const [openId, setOpenId] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const cancel = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);
  const open = useCallback(
    (id: string) => {
      cancel();
      setOpenId(id);
    },
    [cancel],
  );
  const leave = useCallback(
    (id: string) => {
      cancel();
      timer.current = window.setTimeout(() => setOpenId((cur) => (cur === id ? null : cur)), CLOSE_GRACE_MS);
    },
    [cancel],
  );

  useEffect(() => {
    if (!openId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenId(null);
    };
    const onDown = (e: PointerEvent) => {
      const t = (e.target as Element | null)?.closest?.("[data-uc-tile]");
      if (t?.getAttribute("data-uc-tile") !== openId) setOpenId(null);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [openId]);

  useEffect(() => cancel, [cancel]);

  return (
    <div className={styles.grid}>
      {USE_CASES.map((u) => (
        <Tile key={u.id} item={u} open={openId === u.id} onOpen={open} onLeave={leave} onCancelLeave={cancel} />
      ))}
    </div>
  );
}
