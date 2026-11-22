// Flat instrument-panel primitives (DESIGN.md "The Reconciliation Strip").
// Server-safe. Rows default to the matched (reconciled) state, so no-JS and
// reduced-motion visitors see the correct final frame.
import type { ReactNode } from "react";
import styles from "./reconciliation.module.css";

export type ReconPanelProps = {
  /** Mono uppercase header text. */
  title: ReactNode;
  /** Shows a pulsing mint dot (static when reduced motion is requested). */
  live?: boolean;
  children?: ReactNode;
  className?: string;
};

export function ReconPanel({ title, live = false, children, className }: ReconPanelProps) {
  return (
    <div className={[styles.panel, className].filter(Boolean).join(" ")}>
      <div className={styles.head}>
        <span className={styles.title}>{title}</span>
        {live ? <span aria-hidden="true" className={styles.live} /> : null}
      </div>
      <div className={styles.body}>{children}</div>
    </div>
  );
}

export type ReconRowState = "matched" | "unmatched";

export type ReconRowProps = {
  /** Defaults to "matched" (mint border). "unmatched" uses the alarm rose border. */
  state?: ReconRowState;
  /** Cells as a list. Each becomes its own span; the last cell is right-aligned. */
  cells?: ReactNode[];
  /** Alternative to `cells`: arbitrary content laid out in the same row. */
  children?: ReactNode;
  className?: string;
  /** Marks the row as a staggered child of the nearest Reveal (motion only; final state by default). */
  revealChild?: boolean;
};

export function ReconRow({ state = "matched", cells, children, className, revealChild = false }: ReconRowProps) {
  return (
    <div
      data-state={state}
      data-reveal-child={revealChild ? "" : undefined}
      className={[styles.row, className].filter(Boolean).join(" ")}
    >
      {state === "unmatched" ? <span className="sr-only">Unmatched: </span> : null}
      {cells
        ? cells.map((cell, i) => (
            <span key={i} className={styles.cell}>
              {cell}
            </span>
          ))
        : children}
    </div>
  );
}
