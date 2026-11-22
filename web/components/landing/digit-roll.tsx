// DigitRoll: a fixed-width mono figure whose changed digits roll mechanically.
// Adapted from the concept A reel (docs/web/hero-concepts/a-concept.css): each digit
// cell is a 0-9 strip moved by translateY, eased without overshoot. Only changed glyphs move, staggered
// left to right; non-digits swap instantly. Transform transitions only, CSS owned.
// SSR and no-JS render the final value. Reduced motion disables the transition.
'use client';

import { useState, type CSSProperties } from 'react';
import styles from './digit-roll.module.css';

export type DigitRollProps = {
  /** The figure to show, for example "436.46". Amount strings are never reformatted. */
  value: string;
  className?: string;
  /** Length of one reel roll in milliseconds. */
  durationMs?: number;
};

const DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] as const;
const STAGGER_MS = 40;

function isDigit(ch: string | undefined): boolean {
  return ch !== undefined && ch >= '0' && ch <= '9' && ch.length === 1;
}

/** Stagger delay per cell: rolling cells start left to right, 40ms apart. */
function computeDelays(prev: string, next: string): number[] {
  const delays: number[] = [];
  let rank = 0;
  for (let i = 0; i < next.length; i++) {
    const rolls = isDigit(next[i]) && prev[i] !== next[i];
    delays.push(rolls ? rank * STAGGER_MS : 0);
    if (rolls) rank += 1;
  }
  return delays;
}

type RollState = { value: string; delays: number[] };

export function DigitRoll({ value, className, durationMs = 600 }: DigitRollProps) {
  // Derived state: when value changes, recompute stagger delays from the previous value.
  // Rendering with the same value leaves state untouched, so unchanged digits never move.
  const [roll, setRoll] = useState<RollState>(() => ({
    value,
    delays: computeDelays('', value),
  }));
  let current = roll;
  if (roll.value !== value) {
    current = { value, delays: computeDelays(roll.value, value) };
    setRoll(current);
  }

  const rootStyle = { '--roll-ms': `${durationMs}ms` } as CSSProperties;

  return (
    <span className={[styles.root, className].filter(Boolean).join(' ')} style={rootStyle}>
      <span aria-hidden="true" className={styles.visual}>
        {Array.from(value).map((ch, i) => {
          if (!isDigit(ch)) {
            return (
              <span key={i} className={styles.cell}>
                {ch}
              </span>
            );
          }
          const stripStyle = {
            '--d': ch,
            transitionDelay: `${current.delays[i] ?? 0}ms`,
          } as CSSProperties;
          return (
            <span key={i} className={styles.cell}>
              <span className={styles.strip} style={stripStyle}>
                {DIGITS.map((d) => (
                  <span key={d}>{d}</span>
                ))}
              </span>
            </span>
          );
        })}
      </span>
      <span className={styles.sr}>{value}</span>
    </span>
  );
}
