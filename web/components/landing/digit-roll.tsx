'use client';

import { useState, type CSSProperties } from 'react';
import styles from './digit-roll.module.css';

export type DigitRollProps = {
  value: string;
  className?: string;
  durationMs?: number;
};

const DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] as const;
const STAGGER_MS = 40;

function isDigit(ch: string | undefined): boolean {
  return ch !== undefined && ch >= '0' && ch <= '9' && ch.length === 1;
}

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
