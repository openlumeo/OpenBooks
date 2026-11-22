// Section "reframe": confidence is not evidence. The two ledgers stagger row by row on entry.
// The four figures are real amounts from proof-data.ts (RELEASED.rows). The confidence
// tags on the left illustrate a typical extraction tool; they are not engine output and
// are labelled ILLUSTRATIVE.
import { Reveal } from "@/components/motion/reveal";
import { SketchAnnotation } from "@/components/motion/sketch";
import { ParallaxLayer } from "@/components/motion/parallax";
import { PaperStack } from "./paper-stack";
import { Section } from "./section";
import { ReconPanel } from "./reconciliation";
import rec from "./reconciliation.module.css";
import { RELEASED } from "./proof-data";
import styles from "./reframe.module.css";

const FIGURES = RELEASED.rows.slice(0, 4);

/** Illustrative confidence scores shown by a typical extraction tool, one per figure. */
const TYPICAL_SCORES = ["97%", "94%", "99%", "88%"] as const;

export function Reframe() {
  return (
    <Section id="reframe" className={styles.section} heading="Confidence is not evidence.">
      <Reveal y={12} stagger={0.06} className={styles.columns}>
        <div className={styles.column}>
          <p className={styles.statement}>
            Returns its best reading. Attaches a score. Leaves you to check the rest.
          </p>
          <div className={`lp-scroll ${styles.scroll}`} tabIndex={0} role="region" aria-label="A typical extraction tool, illustrative">
            <div className={`${styles.inner} lp-paper`}>
              <ReconPanel
                title={
                  <span className={styles.titleRow}>
                    <span>A TYPICAL EXTRACTION TOOL</span>
                    <span className={styles.illustrative}>ILLUSTRATIVE</span>
                  </span>
                }
              >
                {FIGURES.map((row, i) => (
                  <div key={row.id} className={styles.plainRow} data-reveal-child>
                    <span>{row.date}</span>
                    <span>
                      {row.direction} {row.amount}
                    </span>
                    <span className={styles.score}>{TYPICAL_SCORES[i]}</span>
                  </div>
                ))}
              </ReconPanel>
            </div>
          </div>
        </div>

        <div className={styles.column}>
          <p className={styles.statement}>
            Returns a proven document, or a refusal.{" "}
            <SketchAnnotation kind="scribble" tone="mint">
              Nothing in between.
            </SketchAnnotation>
          </p>
          <div className={`lp-scroll ${styles.scroll}`} tabIndex={0} role="region" aria-label="Open Books, tied out">
            <div className={`${styles.inner} lp-paper`}>
              <ReconPanel
                title={
                  <SketchAnnotation kind="underline" tone="mint" className={styles.openBooks}>
                    OPEN BOOKS
                  </SketchAnnotation>
                }
              >
                {FIGURES.map((row) => (
                  <div key={row.id} data-state="matched" className={rec.row} data-reveal-child>
                    <span className={rec.cell}>{row.date}</span>
                    <span className={rec.cell}>{`${row.direction} ${row.amount}`}</span>
                    <span className={rec.cell}>TIES OUT</span>
                  </div>
                ))}
              </ReconPanel>
            </div>
          </div>
        </div>
      </Reveal>

      <p className={styles.close}>
        A figure at 97% still sends you back to the other 3%. Open Books does not score a document. It checks it.
      </p>

      <div className={styles.interlude}>
        <ParallaxLayer depth={1} className={styles.backdropLayer} aria-hidden="true">
          <div className={styles.backdrop} />
        </ParallaxLayer>
        <PaperStack stamp={false} interactive />
      </div>
    </Section>
  );
}
