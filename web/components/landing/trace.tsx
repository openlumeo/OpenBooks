import { Section } from "./section";
import { TRACE_SAMPLE } from "./trace-data";
import { TracePanel } from "./trace-panel";
import { WipeReveal } from "@/components/motion/wipe-reveal";
import styles from "./trace.module.css";

const tx = TRACE_SAMPLE.transaction;

export function Trace() {
  return (
    <Section id="trace" className={styles.sec} heading="Every figure leads back to its source.">
      <p className={`t-lede ${styles.lede}`}>
        Each value carries its page, box, row, raw text and extraction method. Review a figure the way you would review a
        voucher: by looking at the original.
      </p>
      <WipeReveal from="top" className={styles.reveal}>
        <figure className={`lp-figure ${styles.figure}`} aria-label={`Evidence record ${tx.id}`}>
          <TracePanel />
        </figure>
      </WipeReveal>
    </Section>
  );
}
