// Section 3: a refusal is an answer. Server component.
// Stage per code comes from stageForRefusal (lib/stages.ts). Meanings are
// paraphrased from content/docs/refusals.mdx. Engine messages below are copied
// verbatim from a real engine run (see the comment above ENGINE_REFUSAL_BALANCE).
import { X } from "lucide-react";
import { STAGES, stageForRefusal } from "@/lib/stages";
import type { RefusalCode } from "@/lib/types";
import { Section } from "./section";
import { ReconPanel, ReconRow } from "./reconciliation";
import styles from "./refusals.module.css";

type EngineRefusal = { readonly code: RefusalCode; readonly message: string };

/*
 * Verbatim engine output: error.code and error.message, copied exactly.
 * Command: from the repo root, with PYTHONPATH set to packages/py/openbooks/src and
 * packages/py/openbooks-lab/src (the editable install points at a stale tree), run
 * openbooks_lab.golden.build(root), then openbooks.pipeline.process() on
 *   bad_bank_first_row_amount/in.csv  with Params(opening=Decimal("1000.00"), currency="INR")
 *   bad_bank_no_opening/in.csv        with Params(currency="INR")
 *   bad_unknown_csv_layout/in.csv     with Params()
 * Re-run and paste again if the engine's wording changes.
 */

/** Tampered twin of a balanced bank CSV (first-row debit moved by 0.01). Shown in the refusal panel. */
export const ENGINE_REFUSAL_BALANCE: EngineRefusal = {
  code: "BALANCE_MISMATCH",
  message:
    "batch-1: opening + sum(txns) = closing (expected 5100.40 INR, got 5100.41 INR); batch-1: running balance ties on every row (expected 8 rows, got 0 rows)",
};

/** Balanced file with no stated opening balance. The workspace offers the fix inline. */
export const ENGINE_REFUSAL_MISSING_OPENING: EngineRefusal = {
  code: "PARSE_ERROR",
  message: "statement has no stated opening balance; supply --opening",
};

/** A CSV that matches no known layout. */
export const ENGINE_REFUSAL_UNKNOWN_LAYOUT: EngineRefusal = {
  code: "UNKNOWN_LAYOUT",
  message: "no known layout matches this file",
};

/** The six codes, in stage order, with plain meanings from content/docs/refusals.mdx. */
const CODES: { code: RefusalCode; meaning: string }[] = [
  {
    code: "UNSUPPORTED_INPUT",
    meaning: "The file type, size, encoding or document structure is outside what the engine supports.",
  },
  {
    code: "UNKNOWN_LAYOUT",
    meaning: "No known layout matched the file, or a provider it needs is missing.",
  },
  {
    code: "PARSE_ERROR",
    meaning: "The engine could not read or interpret a required field.",
  },
  {
    code: "LOW_CONFIDENCE",
    meaning: "The OCR or model-assisted reading could not be supported with enough confidence.",
  },
  {
    code: "BALANCE_MISMATCH",
    meaning: "A reconciliation check failed, or the file has no independent balance evidence.",
  },
  {
    code: "OUTPUT_INVALID",
    meaning: "The result failed its contract validation.",
  },
];

const stageLabel = (code: RefusalCode): string => {
  const stage = stageForRefusal(code);
  return STAGES.find((s) => s.id === stage)?.label ?? "Balance";
};

export function Refusals() {
  const panelStage = stageLabel(ENGINE_REFUSAL_BALANCE.code);

  return (
    <Section id="refusals" heading="When it cannot prove a file, it says so.">
      <div className={`lp-scroll ${styles.scroll}`} tabIndex={0} role="region" aria-label="Refusal codes">
        <table className={styles.table}>
          <caption className="sr-only">Refusal codes, the stage each one stops at, and what it means</caption>
          <thead>
            <tr>
              <th scope="col">Code</th>
              <th scope="col">Stops at</th>
              <th scope="col">Meaning</th>
            </tr>
          </thead>
          <tbody>
            {CODES.map(({ code, meaning }) => (
              <tr key={code}>
                <th scope="row" className={styles.code}>
                  {code}
                </th>
                <td className={styles.stage}>{stageLabel(code)}</td>
                <td className={styles.meaning}>{meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={styles.caption}>
        Schema validation is folded into the Balance stage in the workspace, so OUTPUT_INVALID shows as stopping at
        Balance.
      </p>

      <div className={styles.proof}>
        <p className={styles.fix}>
          A refusal names the stage, the code and the engine&apos;s own reason. There is no partial output to
          second-guess, and where the fix is known, such as a missing opening balance, the workspace offers it inline.
        </p>

        <div className={styles.panelWrap}>
          <ReconPanel
            title={
              <span className={styles.panelTitle}>
                <X aria-hidden="true" size={14} strokeWidth={1.75} />
                Refused at {panelStage}
              </span>
            }
          >
            <ReconRow state="unmatched">
              <span className={styles.entry}>
                <span className={styles.entryCode}>{ENGINE_REFUSAL_BALANCE.code}</span>
                <span className={styles.entryMessage}>{ENGINE_REFUSAL_BALANCE.message}</span>
              </span>
            </ReconRow>
          </ReconPanel>
          <p className={styles.panelCaption}>Engine output, unedited.</p>
        </div>
      </div>
    </Section>
  );
}
