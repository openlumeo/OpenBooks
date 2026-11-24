import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HeroStage } from "./hero-stage";
import styles from "./hero.module.css";

export function Hero() {
  return (
    <section id="hero" aria-labelledby="hero-heading" className={styles.hero}>
      <div data-hero-lead className={styles.lead}>
        <div className={styles.leadIn}>
          <h1 id="hero-heading" className={`t-display t-h1 ${styles.title}`}>
            Every figure proven, or{" "}
            refused with a reason.
          </h1>
          <p className={`t-lede ${styles.lede}`}>
            Open Books checks each document&apos;s own arithmetic. Ties out: structured data, with the source of every
            figure.{" "}
            Does not: the reason, never a guess.
          </p>
          <div className={styles.actions}>
            <Link href="/app" className={`btn btn-hero-primary ${styles.primary}`}>
              Open workspace
              <ArrowRight className="btn-arrow" aria-hidden="true" size={16} strokeWidth={1.75} />
            </Link>
            <Link href="/docs" className={`btn btn-secondary-landing ${styles.secondary}`}>
              Read the docs
            </Link>
          </div>
        </div>
      </div>
      <HeroStage />
    </section>
  );
}
