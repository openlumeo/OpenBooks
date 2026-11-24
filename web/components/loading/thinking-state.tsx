"use client";

import { useEffect, useState } from "react";
import styles from "./thinking-state.module.css";

export const THINKING_VERBS = [
  "Reading",
  "Puzzling",
  "Reconciling",
  "Generating",
  "Cross-checking",
  "Tallying",
  "Untangling",
  "Balancing",
  "Pondering",
  "Proving",
] as const;

const VERB_INTERVAL_MS = 2200;
const TICK_MS = 100;
const SECONDS_PER_MINUTE = 60;

const CHEVRON = Array.from({ length: 9 }, (_, index) => {
  const row = Math.floor(index / 3);
  const column = index % 3;
  return (column + Math.abs(row - 1)) * 90;
});

const ORBIT_ORDER = [0, 1, 2, 5, 8, 7, 6, 3];
const ORBIT = Array.from({ length: 9 }, (_, index) => {
  const position = ORBIT_ORDER.indexOf(index);
  return position === -1 ? null : position * 110;
});

const GRIDS = {
  Drive: { delays: CHEVRON, duration: 650 },
  Orbit: { delays: ORBIT, duration: 950 },
} as const;

export type ThinkingVariant = keyof typeof GRIDS;

function PixelGrid({ variant }: { variant: ThinkingVariant }) {
  const { delays, duration } = GRIDS[variant];
  return (
    <span aria-hidden="true" className={styles.grid}>
      {delays.map((delay, index) => (
        <span
          key={index}
          className={`${styles.cell} ${delay === null ? "" : styles.cellOn}`}
          style={
            delay === null
              ? { opacity: 0.07 }
              : { opacity: 0.15, animationDuration: `${duration}ms`, animationDelay: `${delay}ms` }
          }
        />
      ))}
    </span>
  );
}

export function formatElapsed(deciseconds: number): string {
  const total = deciseconds / 10;
  if (total < SECONDS_PER_MINUTE) return `${total.toFixed(1)}s`;
  return `${Math.floor(total / SECONDS_PER_MINUTE)}m ${(total % SECONDS_PER_MINUTE).toFixed(1)}s`;
}

function useElapsed(): string {
  const [deciseconds, setDeciseconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setDeciseconds((value) => value + 1), TICK_MS);
    return () => clearInterval(timer);
  }, []);
  return formatElapsed(deciseconds);
}

function useRotatingVerb(verbs: readonly string[]): string {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (verbs.length < 2) return;
    const timer = setInterval(() => setIndex((value) => (value + 1) % verbs.length), VERB_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [verbs]);
  return verbs[index % verbs.length] ?? "";
}

export default function ThinkingState({
  label,
  verbs = THINKING_VERBS,
  variant = "Drive",
  showElapsed = true,
  className = "",
}: {
  label?: string;
  verbs?: readonly string[];
  variant?: ThinkingVariant;
  showElapsed?: boolean;
  className?: string;
}) {
  const elapsed = useElapsed();
  const verb = useRotatingVerb(verbs);
  const shown = label ?? verb;

  return (
    <span role="status" className={`${styles.root} ${className}`}>
      <PixelGrid variant={variant} />
      <span className="sr-only">{label ?? "Working"}</span>
      <span aria-hidden="true" className={styles.label}>
        <span key={shown} className={styles.verb}>
          {shown}…
        </span>
      </span>
      {showElapsed && (
        <span aria-hidden="true" className={styles.elapsed}>
          {elapsed}
        </span>
      )}
    </span>
  );
}
