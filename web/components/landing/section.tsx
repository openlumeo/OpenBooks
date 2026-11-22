// Shared section wrapper. Heading only, no eyebrow. Server-safe (no hooks).
import type { ReactNode } from "react";
import styles from "./section.module.css";
import { LineReveal } from "@/components/motion/line-reveal";

export type SectionProps = {
  /** Anchor id. When set, the heading is labelled for assistive tech via `${id}-heading`. */
  id?: string;
  /** Rendered inside the h2 with the `t-display t-h2` classes. */
  heading: ReactNode;
  children?: ReactNode;
  className?: string;
};

export function Section({ id, heading, children, className }: SectionProps) {
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section id={id} aria-labelledby={headingId} className={[styles.section, "lp-ledger-rule", className].filter(Boolean).join(" ")}>
      <div className={styles.container}>
        <LineReveal as="h2" id={headingId} className={`t-display t-h2 ${styles.heading}`}>
          {heading}
        </LineReveal>
        {children ? <div className={styles.body}>{children}</div> : null}
      </div>
    </section>
  );
}
