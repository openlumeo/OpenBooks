import Link from "next/link";
import { Reveal } from "@/components/motion/reveal";
import { MEASURED } from "./measured-data";
import { MeasuredCounter } from "./measured-counter";
import { ReconPanel } from "./reconciliation";
import rec from "./reconciliation.module.css";
import { Section } from "./section";
import styles from "./measured.module.css";

const ROWS: { value: number; label: string }[] = [
  { value: MEASURED.endToEndCases, label: "end-to-end cases" },
  { value: MEASURED.released, label: "released" },
  { value: MEASURED.falseAccepts, label: "false accepts" },
  { value: MEASURED.schemaViolations, label: "schema violations" },
];

export function Measured() {
  return (
    <Section id="measured" heading="What the engine has been held to.">
      <Reveal as="div" y={10} stagger={0.08} className={`lp-figure ${styles.wrap}`}>
        <ReconPanel title="END-TO-END">
          {ROWS.map((row) => (
            <div key={row.label} data-state="matched" className={`${rec.row} ${styles.row}`} data-reveal-child>
              <span className={styles.line}>
                <span className={styles.figure}>
                  <MeasuredCounter to={row.value} />
                </span>{" "}
                {row.label}
              </span>
            </div>
          ))}
        </ReconPanel>
        <p className={styles.caption}>
          Results from the engine&apos;s end-to-end test suite.{" "}
          <Link href="/docs/model" className="lp-link">
            See the evidence in the documentation.
          </Link>
        </p>
      </Reveal>
    </Section>
  );
}
