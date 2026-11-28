import { Section } from "./section";
import { AskLaptop } from "./ask-laptop";
import styles from "./ask-demo.module.css";

export function AskDemo() {
  return (
    <Section id="ask" heading="Ask in plain language. The totals come from code.">
      <p className={`t-lede ${styles.lede}`}>
        The model explains and cites. Every sum and count is computed over the released data with exact decimals, and every
        answer names the file and the record.
      </p>
      <div className={styles.stage}>
        <div className={styles.stageInner}>
          <AskLaptop />
        </div>
      </div>
    </Section>
  );
}
