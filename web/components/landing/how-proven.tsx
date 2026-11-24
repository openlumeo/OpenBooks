import { STAGES } from "@/lib/stages";
import type { Stage } from "@/lib/types";
import { ReconPanel, ReconRow } from "./reconciliation";
import styles from "./how-proven.module.css";

export const TRAIL: Stage[] = STAGES.map((s) => s.id);

export const JOB: Record<Exclude<Stage, "validate">, string> = {
  detect: "Identifies the layout from the file itself. An unknown layout stops here.",
  parse: "Reads every row with its page, box and raw text.",
  normalise: "Puts dates, amounts and directions into one schema.",
  balance: "Opening plus transactions equals closing. Running balances tie on every row. Printed totals match.",
};

export const labelOf = (id: Stage): string => STAGES.find((s) => s.id === id)?.label ?? id;

export const CHECKS = [
  "Opening + transactions = closing",
  "Running balance ties on every row",
  "Settlement: gross - fees - tax = net",
  "Printed totals match",
];

export const INDEPENDENT_NOTE =
  "At least one check must be evidence printed in the document, not computed from our own output.";

export const FOOTNOTE = "Optional model checks can only add doubt. They can never cause a release.";

export function ProvenChecks() {
  return (
    <div className={styles.checks}>
      <p className={styles.note}>{INDEPENDENT_NOTE}</p>
      <ReconPanel title="Release checks">
        {CHECKS.map((check) => (
          <ReconRow key={check} cells={[check, labelOf("balance")]} />
        ))}
      </ReconPanel>
      <p className={styles.footnote}>{FOOTNOTE}</p>
    </div>
  );
}
