import Link from "next/link";
import type { RefusalCode } from "@/lib/types";
import { Section } from "./section";
import { UseCaseGrid } from "./usecase-grid";
import styles from "./refusals.module.css";

const CODES: RefusalCode[] = [
  "UNSUPPORTED_INPUT",
  "UNKNOWN_LAYOUT",
  "PARSE_ERROR",
  "LOW_CONFIDENCE",
  "BALANCE_MISMATCH",
  "OUTPUT_INVALID",
];

const FLOW: { label: string; gloss: string }[] = [
  { label: "Detect", gloss: "Which layout is this?" },
  { label: "Parse", gloss: "Read rows and fields" },
  { label: "Normalise", gloss: "Decimal money, ISO dates" },
  { label: "Balance", gloss: "Do the numbers tie?" },
];

export function Refusals() {
  return (
    <Section id="use-cases" className={styles.sec} heading="What developers build on it.">
      <p className={styles.lede}>
        You send a financial file. You get back one verified <code>openbooks.v1</code> JSON, or a typed refusal that
        says why. Never a guess.
      </p>

      <ol className={styles.flow} aria-label="What happens to a file">
        <li className={styles.flowEnd}>
          <span className={styles.flowLabel}>File</span>
          <span className={styles.flowGloss}>CSV, PDF, scan</span>
        </li>
        {FLOW.map((f) => (
          <li key={f.label} className={styles.flowStep}>
            <span className={styles.flowLabel}>{f.label}</span>
            <span className={styles.flowGloss}>{f.gloss}</span>
          </li>
        ))}
        <li className={`${styles.flowEnd} ${styles.flowOut}`}>
          <span className={styles.flowLabel}>Released JSON</span>
          <span className={styles.flowGloss}>or a typed refusal</span>
        </li>
      </ol>

      <UseCaseGrid />

      <p className={styles.codes}>
        <span className={styles.codesLabel}>Six refusal codes</span>
        <span className={styles.codeList}>
          {CODES.map((c) => (
            <code key={c}>{c}</code>
          ))}
        </span>
        <Link href="/docs/refusals" className={styles.codesLink}>
          What each one means
        </Link>
      </p>
    </Section>
  );
}
