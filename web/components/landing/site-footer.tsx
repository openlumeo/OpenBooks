// Sober landing footer. Claims are limited to the processing statement and the model link.
import Link from "next/link";
import { BrandLockup } from "@/components/brand/brand-lockup";
import styles from "./site-footer.module.css";

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
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
