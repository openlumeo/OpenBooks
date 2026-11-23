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
  Drive: { delays: CHEVRON, duration: 650, round: false },
  Dots: { delays: CHEVRON, duration: 650, round: true },
  Orbit: { delays: ORBIT, duration: 950, round: false },
} as const;

const BAR_HEIGHTS = [12, 20, 28, 34, 34, 28, 20, 12];
const BAR_WIDTH = 5;
const BAR_GAP = 3;
const MASCOT_HEIGHT = 36;
const MASCOT_WIDTH = BAR_HEIGHTS.length * BAR_WIDTH + (BAR_HEIGHTS.length - 1) * BAR_GAP;
const EYE_BARS = [3, 4];
const ACCENT_BARS = [0, 7];

export type ThinkingVariant = "Mascot" | "Drive" | "Dots" | "Orbit";

function PixelGrid({ variant }: { variant: Exclude<ThinkingVariant, "Mascot"> }) {
  const { delays, duration, round } = GRIDS[variant];
  return (
    <span aria-hidden="true" className={styles.grid}>
      {delays.map((delay, index) => (
        <span
          key={index}
          className={`${styles.cell} ${round ? styles.round : ""} ${delay === null ? "" : styles.cellOn}`}
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

function Mascot() {
  return (
    <svg
      aria-hidden="true"
      className={styles.mascot}
      width={MASCOT_WIDTH}
      height={MASCOT_HEIGHT}
      viewBox={`0 0 ${MASCOT_WIDTH} ${MASCOT_HEIGHT}`}
    >
      {BAR_HEIGHTS.map((height, index) => {
        const x = index * (BAR_WIDTH + BAR_GAP);
        const y = MASCOT_HEIGHT - height;
        return (
          <g key={index}>
            <rect
              className={`${styles.bar} ${ACCENT_BARS.includes(index) ? styles.barAccent : ""}`}
              x={x}
              y={y}
              width={BAR_WIDTH}
              height={height}
              rx={BAR_WIDTH / 2}
              style={{ animationDelay: `${index * 90}ms` }}
            />
            {EYE_BARS.includes(index) && (
              <g>
                <ellipse className={styles.eye} cx={x + BAR_WIDTH / 2} cy={y + 9} rx={2.1} ry={2.6} />
                <circle className={styles.pupil} cx={x + BAR_WIDTH / 2} cy={y + 9.4} r={1} />
              </g>
            )}
          </g>
        );
      })}
    </svg>
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
  variant = "Mascot",
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
      {variant === "Mascot" ? <Mascot /> : <PixelGrid variant={variant} />}
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
