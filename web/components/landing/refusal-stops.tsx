'use client';
import { useLayoutEffect, useRef, useState } from 'react';
import { STAGES, stageForRefusal } from '@/lib/stages';
import type { RefusalCode, Stage } from '@/lib/types';
import { Flip, DESKTOP_MOTION } from '@/components/motion/gsap-setup';
import { RefusalStamp } from './refusal-stamp';
import styles from './refusal-stops.module.css';

type FlipState = ReturnType<typeof Flip.getState>;

const shownStage = (code: RefusalCode): Stage => {
  const id = stageForRefusal(code);
  return STAGES.some((s) => s.id === id) ? id : 'balance';
};

export function RefusalStops({ codes, initial }: { codes: readonly RefusalCode[]; initial: RefusalCode }) {
  const [selected, setSelected] = useState<RefusalCode>(initial);
  const marker = useRef<HTMLSpanElement>(null);
  const pending = useRef<FlipState | null>(null);
  const stage = shownStage(selected);
  const stageName = STAGES.find((s) => s.id === stage)?.label ?? 'Balance';

  useLayoutEffect(() => {
    const state = pending.current;
    pending.current = null;
    if (state && marker.current) Flip.from(state, { targets: marker.current, duration: 0.5, ease: 'power3.inOut', scale: true });
  }, [selected]);

  const choose = (code: RefusalCode) => {
    if (marker.current && window.matchMedia(DESKTOP_MOTION).matches) pending.current = Flip.getState(marker.current);
    setSelected(code);
  };

  return (
    <div className={styles.stops}>
      <div role="group" aria-label="Refusal code" className={styles.codes}>
        {codes.map((code) => (
          <button key={code} type="button" aria-pressed={code === selected} onClick={() => choose(code)} className={styles.code}>{code}</button>
        ))}
      </div>
      <ol className={styles.stages} aria-label="Pipeline stages">
        {STAGES.map((s) => (
          <li key={s.id} className={styles.stage} aria-current={s.id === stage ? 'step' : undefined}>
            <span>{s.label}</span>
            {s.id === stage ? <span ref={marker} data-flip-id="refusal-mark" className={styles.mark}><RefusalStamp /></span> : null}
          </li>
        ))}
      </ol>
      <p aria-live="polite" className="sr-only">{selected}: {stageName}</p>
    </div>
  );
}
