import fs from "node:fs";
import path from "node:path";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal } from "@/components/motion/reveal";
import { AgentQuickStart } from "@/components/onboard/agent-onboarding";
import { BalanceLine } from "./balance-line";
import { LoopFrame, type LoopSource } from "./media-frame";
import styles from "./final-cta.module.css";

const MOTION_DIR = path.join(process.cwd(), "public", "motion");
const MIN_VIDEO_BYTES = 100_000;

function fileSize(name: string): number {
  try {
    return fs.statSync(path.join(MOTION_DIR, name)).size;
  } catch {
    return 0;
  }
}

function loopIsRendered(): boolean {
  return (
    fileSize("hero-loop.webm") > MIN_VIDEO_BYTES &&
    fileSize("hero-loop.mp4") > MIN_VIDEO_BYTES &&
    fileSize("hero-loop-poster.jpg") > 0
  );
}

const LOOP_SOURCES: readonly LoopSource[] = [
  { src: "/motion/hero-loop.webm", type: "video/webm" },
  { src: "/motion/hero-loop.mp4", type: "video/mp4" },
];

export function FinalCta() {
  const hasLoop = loopIsRendered();

  return (
    <section id="start" aria-labelledby="start-heading" className={styles.band}>
      <div className={`${styles.container} ${hasLoop ? styles.withLoop : ""}`}>
        <Reveal as="div" y={14} stagger={0.1} className={styles.copy}>
          <h2 id="start-heading" data-reveal-child className={`t-display t-h2 ${styles.heading}`}>
            Bring one client&apos;s month-end. See what{" "}
            ties out.
          </h2>
          <p data-reveal-child className={`t-lede ${styles.lede}`}>
            Open the workspace, drop a file, and watch it released or refused with the reason on the page.
          </p>
          <BalanceLine />
          <div data-reveal-child className={styles.actions}>
            <Link href="/app" className={`btn btn-primary-landing ${styles.action}`}>
              Open workspace
              <ArrowRight aria-hidden="true" size={16} strokeWidth={1.75} className="btn-arrow" />
            </Link>
            <Link href="/docs" className={`btn btn-secondary-landing ${styles.action}`}>
              Read the docs
            </Link>
          </div>
          <div data-reveal-child className={styles.agentBlock}>
            <AgentQuickStart />
          </div>
        </Reveal>

        {hasLoop ? (
          <Reveal as="div" y={24} delay={0.2} className={styles.media}>
            <LoopFrame
              poster="/motion/hero-loop-poster.jpg"
              sources={LOOP_SOURCES}
              caption="Release in progress"
              label="Looping render of a released statement: each row ties out to the closing balance and the RELEASED stamp lands."
            />
          </Reveal>
        ) : null}
      </div>
    </section>
  );
}
