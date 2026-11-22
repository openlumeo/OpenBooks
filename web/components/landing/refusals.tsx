import { X } from "lucide-react";
import { STAGES, stageForRefusal } from "@/lib/stages";
import type { RefusalCode } from "@/lib/types";
import { Section } from "./section";
import { ReconPanel, ReconRow } from "./reconciliation";
import { RefusalStamp } from "./refusal-stamp";
import { RefusalPush } from "./refusal-push";
import styles from "./refusals.module.css";

type EngineRefusal = { readonly code: RefusalCode; readonly message: string };


export const ENGINE_REFUSAL_BALANCE: EngineRefusal = {
  code: "BALANCE_MISMATCH",
  message:
    "batch-1: opening + sum(txns) = closing (expected 5100.40 INR, got 5100.41 INR); batch-1: running balance ties on every row (expected 8 rows, got 0 rows)",
};

export const ENGINE_REFUSAL_MISSING_OPENING: EngineRefusal = {
  code: "PARSE_ERROR",
  message: "statement has no stated opening balance; supply --opening",
};

export const ENGINE_REFUSAL_UNKNOWN_LAYOUT: EngineRefusal = {
  code: "UNKNOWN_LAYOUT",
  message: "no known layout matches this file",
};

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
                  <span className={styles.codeCell}>
                    <RefusalStamp />
                    {code}
                  </span>
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

      <RefusalPush className={styles.proof}>
        <p className={styles.fix}>
          A refusal names the stage, the code and the engine&apos;s own reason. There is no partial output to
          second-guess, and where the fix is known, such as a missing opening balance, the workspace offers it inline.
        </p>

        <div className={styles.panelWrap} data-push="">
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
          <p className={styles.panelCaption} data-push-caption="">Engine output, unedited.</p>
        </div>
      </RefusalPush>
    </Section>
  );
}
