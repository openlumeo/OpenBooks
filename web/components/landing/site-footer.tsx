import Link from "next/link";
import { BrandLockup } from "@/components/brand/brand-lockup";
import { DotWordmark } from "./dot-wordmark";
import styles from "./site-footer.module.css";

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.top}>
          <div className={styles.brand}>
            <BrandLockup markSize={24} />
            <p className={styles.statement}>
              Files are processed in memory and not stored on the server. Thread history stays in your browser.
            </p>
          </div>
          <nav aria-label="Footer" className={styles.cols}>
            <div className={styles.col}>
              <h2 className={styles.heading}>Product</h2>
              <ul className={styles.list}>
                <li>
                  <Link href="/app" className={styles.link}>
                    Workspace
                  </Link>
                </li>
                <li>
                  <Link href="/get-started" className={styles.link}>
                    Get started
                  </Link>
                </li>
                <li>
                  <Link href="/benchmark" className={styles.link}>
                    Benchmark
                  </Link>
                </li>
              </ul>
            </div>
            <div className={styles.col}>
              <h2 className={styles.heading}>Developers</h2>
              <ul className={styles.list}>
                <li>
                  <Link href="/docs" className={styles.link}>
                    Docs
                  </Link>
                </li>
                <li>
                  <Link href="/docs/model" className={styles.link}>
                    Model and limits
                  </Link>
                </li>
                <li>
                  <Link href="/llms.txt" className={styles.link}>
                    Docs for AI agents
                  </Link>
                </li>
                <li>
                  <a
                    href="https://mcprush.com/to/openbooks-mcp?ref=badge"
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.link}
                  >
                    MCP server
                  </a>
                </li>
              </ul>
            </div>
          </nav>
        </div>
        <DotWordmark word="OpenBooks" className={styles.wordmark} />
        <div className={styles.bottom}>
          <span>&copy; {year} Lumeo</span>
        </div>
      </div>
    </footer>
  );
}
