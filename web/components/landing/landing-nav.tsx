"use client";

// Floating primary nav. Expanded at the top of the page, shrinks once the
// page scrolls past the NavSentinel. IntersectionObserver only, no scroll
// listener. Without JS the nav renders expanded and fully functional.
import Link from "next/link";
import { useEffect, useState } from "react";
import { BrandLockup } from "@/components/brand/brand-lockup";
import { ThemeToggle } from "@/components/brand/theme-toggle";
import styles from "./landing-nav.module.css";

/**
 * 1px marker placed at the very top of the landing page. LandingNav watches it:
 * once it leaves the viewport the nav shrinks. Safe to render from a server component.
 */
export function NavSentinel() {
  return <div aria-hidden="true" data-nav-sentinel className="lp-nav-sentinel" />;
}

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const sentinel = document.querySelector("[data-nav-sentinel]");
    if (!sentinel || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      const entry = entries[entries.length - 1];
      if (entry) setScrolled(!entry.isIntersecting);
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  return (
    <nav
      aria-label="Primary"
      data-scrolled={scrolled ? "true" : "false"}
      className={`lp-glass lp-glass--blur ${styles.nav}`}
    >
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label="Open Books by Lumeo, home">
          <BrandLockup markSize={scrolled ? 22 : 28} />
        </Link>
        <div className={styles.actions}>
          <Link href="/docs" className={styles.link}>
            Docs
          </Link>
          <Link href="/app" className={`btn btn-primary-landing ${styles.cta}`}>
            Open workspace
          </Link>
          <ThemeToggle className={styles.toggle} />
        </div>
      </div>
    </nav>
  );
}
