import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal } from "@/components/motion/reveal";
import styles from "./final-cta.module.css";

export function FinalCta() {
  return (
    <section id="start" aria-labelledby="start-heading" className={styles.band}>
      <Reveal as="div" y={14} stagger={0.1} className={styles.inner}>
        <h2 id="start-heading" data-reveal-child className={`t-display t-h2 ${styles.heading}`}>
          Try it on one client&apos;s statement.
        </h2>
        <p data-reveal-child className={`t-lede ${styles.lede}`}>
          See what ties out.
        </p>
        <div data-reveal-child className={styles.actions}>
          <Link href="/app" className={`btn btn-hero-primary ${styles.action}`}>
            Open workspace
            <ArrowRight className="btn-arrow" aria-hidden="true" size={16} strokeWidth={1.75} />
          </Link>
          <Link href="/docs" className={`btn btn-secondary-landing ${styles.action}`}>
            Read the docs
          </Link>
        </div>
      </Reveal>
    </section>
  );
}
