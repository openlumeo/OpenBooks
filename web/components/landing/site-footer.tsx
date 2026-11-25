import Link from "next/link";
import { BrandLockup } from "@/components/brand/brand-lockup";
import { FormatMarquee } from "./format-marquee";
import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <FormatMarquee />
      <svg
        className={styles.closeRule}
        viewBox="0 0 100 6"
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <path d="M0 1 H100" />
        <path d="M0 5 H100" />
      </svg>
      <div className={styles.inner}>
        <div className={styles.left}>
          <BrandLockup markSize={24} />
          <Link href="/docs/model" className={`lp-link ${styles.maturity}`}>
            Model and limits
          </Link>
          <p className={styles.statement}>
            Files are processed in memory and not stored on the server. Thread history stays in your browser.
          </p>
        </div>
        <nav aria-label="Footer" className={styles.links}>
          <Link href="/docs" className={styles.link}>
            Docs
          </Link>
          <Link href="/benchmark" className={styles.link}>
            Benchmark
          </Link>
          <Link href="/blog" className={styles.link}>
            Blog
          </Link>
          <Link href="/app" className={styles.link}>
            Workspace
          </Link>
          <Link href="/llms.txt" className={styles.link}>
            Docs for AI agents
          </Link>
        </nav>
      </div>
    </footer>
  );
}
