"use client";

import { useEffect, useRef } from "react";
import styles from "./hero-flip.module.css";

// The closing period lives inside the last slot, so the space reserved for the
// longer word falls after it, at the end of the line, not before the period.
const PAIRS = [
  ["figure", "claim"],
  ["provenance.", "traceability."],
] as const;

const INTERVAL = 3200;
const DURATION = 560;
const STAGGER = 80;
const EASE = "cubic-bezier(0.16, 1, 0.3, 1)";

function Slot({ words, index }: { words: readonly [string, string]; index: number }) {
  return (
    <span className={styles.slot} data-flip-slot={index}>
      {words.map((w, i) => (
        <span key={w} className={styles.word} data-w={i}>
          {w.endsWith(".") ? (
            <>
              {w.slice(0, -1)}
              <span className={styles.dot}>.</span>
            </>
          ) : (
            w
          )}
        </span>
      ))}
    </span>
  );
}

/**
 * Hero headline. Accessible text is the full statement once; the animated
 * line is aria-hidden. Without JS or under reduced motion the two sentences
 * are shown statically on two lines.
 */
export function HeroFlip() {
  const rootRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) return;

    let state = 0;
    let timer: number | undefined;
    let inView = true;
    let visible = !document.hidden;
    const slots = Array.from(root.querySelectorAll<HTMLElement>("[data-flip-slot]"));

    const flip = () => {
      const next = state === 0 ? 1 : 0;
      slots.forEach((slot, i) => {
        const out = slot.querySelector<HTMLElement>(`[data-w="${state}"]`);
        const inc = slot.querySelector<HTMLElement>(`[data-w="${next}"]`);
        const opts = { duration: DURATION, delay: i * STAGGER, easing: EASE, fill: "both" as const };
        out?.animate(
          [
            { transform: "translateY(0)", opacity: 1 },
            { transform: "translateY(-100%)", opacity: 0 },
          ],
          { ...opts, fill: "backwards" },
        );
        inc?.animate(
          [
            { transform: "translateY(100%)", opacity: 0 },
            { transform: "translateY(0)", opacity: 1 },
          ],
          { ...opts, fill: "backwards" },
        );
      });
      state = next;
      root.dataset.state = String(state);
    };

    const stop = () => {
      if (timer !== undefined) window.clearInterval(timer);
      timer = undefined;
    };
    const sync = () => {
      stop();
      if (inView && visible && !mq.matches) timer = window.setInterval(flip, INTERVAL);
    };

    const io = new IntersectionObserver(
      (entries) => {
        inView = entries[entries.length - 1]?.isIntersecting ?? true;
        sync();
      },
      { threshold: 0.1 },
    );
    io.observe(root);
    const onVis = () => {
      visible = !document.hidden;
      sync();
    };
    document.addEventListener("visibilitychange", onVis);
    mq.addEventListener("change", sync);
    sync();

    return () => {
      stop();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      mq.removeEventListener("change", sync);
    };
  }, []);

  return (
    <>
      <span className={styles.sr}>No figure without provenance. No claim without traceability.</span>
      <span ref={rootRef} className={styles.live} data-flip-live data-state="0" aria-hidden="true">
        No <Slot words={PAIRS[0]} index={0} /> without <Slot words={PAIRS[1]} index={1} />
      </span>
      <span className={styles.static} data-flip-static aria-hidden="true">
        <span className={styles.line}>No figure without provenance.</span>
        <span className={styles.line}>No claim without traceability.</span>
      </span>
      <noscript>
        <style>{`[data-flip-live]{display:none!important}[data-flip-static]{display:block!important}`}</style>
      </noscript>
    </>
  );
}
