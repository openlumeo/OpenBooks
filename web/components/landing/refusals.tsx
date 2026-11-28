import { Section } from "./section";
import { UseCaseGrid } from "./usecase-grid";
import styles from "./refusals.module.css";

const FLOW: { label: string; gloss: string }[] = [
  { label: "Detect", gloss: "Which layout is this?" },
  { label: "Parse", gloss: "Read rows and fields" },
  { label: "Normalise", gloss: "Decimal money, ISO dates" },
  { label: "Balance", gloss: "Do the numbers tie?" },
];

export function Refusals() {
  return (
    <Section id="use-cases" className={styles.sec} heading="How you can use Open Books.">
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
    </Section>
  );
}
