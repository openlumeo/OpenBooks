// The hero's object: the released statement beside its tampered twin, both
// rendered from real engine output (see proof-data.ts). Server-safe, no hooks.
// Rows default to their final state; the stage animation runs only under
// prefers-reduced-motion: no-preference (proof-pair.module.css).
import type { CSSProperties, ReactNode } from "react";
import { ReconPanel, ReconRow } from "./reconciliation";
import { ENGINE_STAGES, RELEASED, TAMPERED, type LedgerLine } from "./proof-data";
import styles from "./proof-pair.module.css";

export type ProofPairProps = {
  className?: string;
};

type StageState = "pass" | "fail" | "not-run";

/** Display label for the refused twin. The file on disk is statement-tampered.csv. */
const REFUSED_FILE_LABEL = "statement.csv, one balance altered";

const STATE_LABEL: Record<StageState, string> = {
  pass: "PASS",
  fail: "FAIL",
  "not-run": "NOT RUN",
};

function StageTrail({
  reached,
  failed,
  animate,
  label,
}: {
  reached: readonly string[];
  failed?: string;
  animate: boolean;
  label: string;
}) {
  return (
    <ol className={styles.trail} aria-label={label} data-animate={animate ? "true" : "false"}>
      {ENGINE_STAGES.map((name, index) => {
        const key = name.toLowerCase();
        const state: StageState = reached.includes(key)
          ? "pass"
          : failed === name
            ? "fail"
            : "not-run";
        const style = { "--i": String(index) } as unknown as CSSProperties;
        return (
          <li key={key} className={styles.stage} data-state={state} style={style}>
            <span className={styles.stageName}>{name}</span>
            <span className={styles.stageStatus}>{STATE_LABEL[state]}</span>
          </li>
        );
      })}
    </ol>
  );
}

function Ledger({
  label,
  rows,
  hiddenCount,
  unmatchedId,
  closing,
  children,
}: {
  label: string;
  rows: readonly LedgerLine[];
  hiddenCount: number;
  unmatchedId?: string;
  /** Engine closing balance. Omitted for a refused file, which has no closing claim. */
  closing?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className={`lp-scroll ${styles.scroll}`}
      tabIndex={0}
      role="region"
      aria-label={`${label}, ledger rows`}
    >
      <div className={styles.ledger}>
        <div className={styles.ledgerHead} aria-hidden="true">
          <span>Date</span>
          <span>Row</span>
          <span>Amount</span>
          <span>Balance</span>
        </div>
        <ReconRow className={styles.line} revealChild cells={["", "OPENING", "", RELEASED.opening]} />
        {rows.map((row) => (
          <ReconRow
            key={row.id}
            revealChild
            className={styles.line}
            state={row.id === unmatchedId ? "unmatched" : "matched"}
            cells={[row.date, row.description, `${row.direction} ${row.amount}`, row.balance]}
          />
        ))}
        {hiddenCount > 0 ? <p className={styles.note}>+{hiddenCount} more rows</p> : null}
        {closing !== undefined ? (
          <ReconRow className={styles.line} revealChild cells={["", "CLOSING", "", closing]} />
        ) : null}
        {children}
      </div>
    </div>
  );
}

export function ProofPair({ className }: ProofPairProps) {
  const released = RELEASED;
  const refused = TAMPERED;
  const equation = `${released.opening} + ${released.creditTotal} - ${released.debitTotal} = ${released.closing}`;

  return (
    <div className={[styles.pair, className].filter(Boolean).join(" ")}>
      <figure
        className={`lp-figure ${styles.figure}`}
        aria-label={`Released statement, ${released.fileName}: ${released.transactionCount} transactions tie to the closing balance`}
      >
        <ReconPanel className={styles.panel} title={`${released.fileName} · RELEASED`}>
          <div className={styles.content}>
            <StageTrail reached={released.stagesReached} animate label="Engine stages, released file" />
            <Ledger
              label="Released statement"
              rows={released.rows}
              hiddenCount={released.hiddenRowCount}
              closing={released.closing}
            >
              <ReconRow className={`${styles.line} ${styles.equation}`} revealChild>
                <span>{equation}</span>
                {released.equationAssertion.independent ? (
                  <span className={styles.tag}>INDEPENDENT</span>
                ) : null}
              </ReconRow>
            </Ledger>
            <p className={styles.stamp}>RELEASED</p>
          </div>
        </ReconPanel>
      </figure>

      <figure
        className={`lp-figure ${styles.figure}`}
        aria-label={`Refused twin, ${REFUSED_FILE_LABEL}: ${refused.code}`}
      >
        <ReconPanel className={styles.panel} title={`${REFUSED_FILE_LABEL} · REFUSED`}>
          <div className={styles.content}>
            <StageTrail
              reached={refused.stagesReached}
              failed={refused.failedStage}
              animate={false}
              label="Engine stages, refused file"
            />
            <Ledger
              label="Refused statement"
              rows={refused.rows}
              hiddenCount={refused.hiddenRowCount}
              unmatchedId={refused.offendingRowId}
            />
            <div className={styles.verdict}>
              <p className={styles.verdictLine}>
                REFUSED · {refused.code}
              </p>
              <p className={styles.message}>{refused.message}</p>
            </div>
          </div>
        </ReconPanel>
      </figure>
    </div>
  );
}
