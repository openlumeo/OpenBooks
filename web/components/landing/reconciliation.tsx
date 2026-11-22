import type { ReactNode } from "react";
import styles from "./reconciliation.module.css";

export type ReconPanelProps = {
  title: ReactNode;
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
  state?: ReconRowState;
  cells?: ReactNode[];
  children?: ReactNode;
  className?: string;
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
