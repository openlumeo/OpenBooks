import { STAGES } from "@/lib/stages";
import type { Stage } from "@/lib/types";
import { RELEASED } from "./proof-data";
import styles from "./how-proven.module.css";

export const TRAIL: Stage[] = STAGES.map((s) => s.id);

type StepId = Exclude<Stage, "validate">;

/** The plain question each of the four checks answers. */
export const QUESTION: Record<StepId, string> = {
  detect: "Do we know this layout?",
  parse: "Can every row be read, with its source?",
  normalise: "Do dates, amounts and directions fit one schema?",
  balance: "Do the numbers add up?",
};

export const JOB: Record<StepId, string> = {
  detect: "The layout is identified from the file itself. An unknown layout stops here.",
  parse: "Every row is read with its page, box and raw text.",
  normalise: "Dates, amounts and directions are put into one schema.",
  balance: "Four arithmetic proofs run here. They are listed below.",
};

export const labelOf = (id: Stage): string => STAGES.find((s) => s.id === id)?.label ?? id;

const first = RELEASED.rows[0]!;

export const PROOFS = [
  {
    name: "Opening to closing",
    plain: "The opening balance plus every transaction must equal the closing balance.",
    example: `${RELEASED.opening} + ${RELEASED.creditTotal} - ${RELEASED.debitTotal} = ${RELEASED.closing}`,
    applies: "Bank statements",
  },
  {
    name: "Running balance",
    plain: "After each row, the balance shown must equal the previous balance plus or minus that row.",
    example: `${RELEASED.opening} + ${first.amount} = ${first.balance}`,
    applies: "Bank statements",
  },
  {
    name: "Settlement net",
    plain: "Gross sales, minus fees, minus tax, must equal the net amount paid out.",
    example: "gross - fees - tax = net",
    applies: "Payment settlements",
  },
  {
    name: "Printed totals",
    plain: "If the file prints its own totals, they must equal the totals we add up from its rows.",
    example: "printed total = sum of rows",
    applies: "Any file that prints totals",
  },
] as const;

export const INDEPENDENT_NOTE =
  "At least one proof must use a number the document prints itself, such as its stated closing balance. That way a file is never checked only against our own output.";

export const FOOTNOTE =
  "Optional OCR or model confidence can only flag a file for doubt (LOW_CONFIDENCE). It can never release one.";

export function ProvenChecks() {
  return (
    <div className={styles.checks}>
      <div className={styles.lead}>
        <span className={styles.badge} aria-hidden="true">
          4
        </span>
        <div className={styles.leadText}>
          <h3 className={styles.title}>What the {labelOf("balance")} check proves</h3>
          <p className={styles.sub}>
            {labelOf("balance")} is the fourth check. It runs these four proofs. Each one applies to the file types
            named beside it.
          </p>
        </div>
      </div>

      <ol className={styles.proofs} aria-label="Balance proofs">
        {PROOFS.map((p, i) => (
          <li key={p.name} className={styles.proof}>
            <span className={styles.num}>{String(i + 1).padStart(2, "0")}</span>
            <div className={styles.body}>
              <p className={styles.name}>{p.name}</p>
              <p className={styles.plain}>{p.plain}</p>
              <p className={styles.example}>{p.example}</p>
              <p className={styles.applies}>Applies to: {p.applies}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className={styles.notes}>
        <p className={styles.note}>{INDEPENDENT_NOTE}</p>
        <p className={styles.note}>{FOOTNOTE}</p>
      </div>
    </div>
  );
}
