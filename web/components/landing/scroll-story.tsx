"use client";

import { useRef } from "react";
import { gsap, useGSAP } from "@/components/motion/gsap-setup";
import { Reveal } from "@/components/motion/reveal";
import { ScrambleLabel } from "@/components/motion/scramble-label";
import { Section } from "./section";
import { DeviceFrame } from "./device-frame";
import { JOB, QUESTION, ProvenChecks, TRAIL, labelOf } from "./how-proven";
import { RELEASED } from "./proof-data";
import type { Stage } from "@/lib/types";
import styles from "./scroll-story.module.css";

const STORY_MOTION = "(min-width: 900px) and (prefers-reduced-motion: no-preference)";
const PIN_VIEWPORTS = 3;

const DIRECTION_WORD: Record<"CR" | "DR", string> = { CR: "credit", DR: "debit" };

function Col({ raw, norm, right = false }: { raw: string; norm: string; right?: boolean }) {
  return (
    <span className={`${styles.cell} ${right ? styles.num : ""}`}>
      <span data-fx="raw-head">{raw}</span>
      <span data-fx="norm-head" className={styles.schema}>
        {norm}
      </span>
    </span>
  );
}

function LedgerScreen() {
  return (
    <div className={styles.ledger}>
      <div className={styles.bar}>
        <span className={styles.file} data-fx="detect">
          {RELEASED.fileName}
        </span>
        <span className={styles.layout} data-fx="detect">
          bank_csv.v1 · detected
        </span>
      </div>

      <div className={styles.table}>
        <div className={`${styles.head} ${styles.cols}`}>
          <Col raw="Date" norm="date" />
          <Col raw="Row" norm="txn_id" />
          <Col raw="Dir" norm="direction" />
          <Col raw="Amount" norm="amount" right />
          <Col raw="Balance" norm="balance" right />
        </div>
        {RELEASED.rows.map((row) => (
          <div key={row.id} className={`${styles.row} ${styles.cols}`} data-state="matched" data-fx="row">
            <span>{row.date}</span>
            <span className={styles.chip}>{row.id}</span>
            <span className={styles.cell}>
              <span data-fx="dir-raw">{row.direction}</span>
              <span data-fx="dir-norm">{DIRECTION_WORD[row.direction]}</span>
            </span>
            <span className={styles.num}>{row.amount}</span>
            <span className={styles.num}>{row.balance}</span>
          </div>
        ))}
      </div>

      <div className={styles.equation}>
        <span data-fx="eq">
          Opening <b>{RELEASED.opening}</b>
        </span>
        <span data-fx="eq">
          + credits <b>{RELEASED.creditTotal}</b>
        </span>
        <span data-fx="eq">
          - debits <b>{RELEASED.debitTotal}</b>
        </span>
        <span data-fx="eq">
          = Closing <b>{RELEASED.closing}</b>
        </span>
      </div>

      <div className={styles.verdict}>
        <span className={styles.tie} data-fx="tie">
          Ties out
        </span>
        <span className={styles.stamp} data-fx="stamp">
          RELEASED
        </span>
      </div>
    </div>
  );
}

export function ScrollStory() {
  const rootRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const root = rootRef.current;
      if (!root) return;

      gsap.matchMedia().add(STORY_MOTION, () => {
        const q = (selector: string) => gsap.utils.toArray<HTMLElement>(selector, root);
        const steps = q("[data-step]");
        const rule = q("[data-fx='rule']");
        const detect = q("[data-fx='detect']");
        const rows = q("[data-fx='row']");
        const rawHead = q("[data-fx='raw-head']");
        const normHead = q("[data-fx='norm-head']");
        const dirRaw = q("[data-fx='dir-raw']");
        const dirNorm = q("[data-fx='dir-norm']");
        const eq = q("[data-fx='eq']");
        const tie = q("[data-fx='tie']");
        const stamp = q("[data-fx='stamp']");

        gsap.set(steps, { opacity: 0.35 });
        gsap.set(rule, { scaleY: 0 });
        gsap.set(detect, { opacity: 0, y: 6 });
        gsap.set(rows, { opacity: 0, y: 8 });
        gsap.set(rawHead, { opacity: 1 });
        gsap.set(dirRaw, { opacity: 1 });
        gsap.set(normHead, { opacity: 0, y: 6 });
        gsap.set(dirNorm, { opacity: 0 });
        gsap.set(eq, { opacity: 0, y: 6 });
        gsap.set(tie, { opacity: 0 });
        gsap.set(stamp, { opacity: 0, scale: 1.5 });

        const tl = gsap.timeline({
          defaults: { ease: "none" },
          scrollTrigger: {
            trigger: root,
            start: "center center",
            end: () => `+=${Math.round(window.innerHeight * PIN_VIEWPORTS)}`,
            pin: true,
            anticipatePin: 1,
            scrub: 0.6,
            invalidateOnRefresh: true,
          },
        });

        tl.to(rule, { scaleY: 1, duration: steps.length }, 0);
        steps.forEach((step, i) => {
          tl.to(step, { opacity: 1, duration: 0.5 }, i);
          const previous = steps[i - 1];
          if (previous) tl.to(previous, { opacity: 0.35, duration: 0.5 }, i);
        });

        tl.to(detect, { opacity: 1, y: 0, duration: 0.4, stagger: 0.15 }, 0.1);

        tl.to(rows, { opacity: 1, y: 0, duration: 0.4, stagger: 0.12 }, 1.1);

        tl.to(rawHead, { opacity: 0, duration: 0.2 }, 2.0);
        tl.to(normHead, { opacity: 1, y: 0, duration: 0.3 }, 2.25);
        tl.to(dirRaw, { opacity: 0, duration: 0.15 }, 2.6);
        tl.to(dirNorm, { opacity: 1, duration: 0.15 }, 2.8);

        tl.to(eq, { opacity: 1, y: 0, duration: 0.3, stagger: 0.12 }, 3.05);
        tl.to(tie, { opacity: 1, duration: 0.2 }, 3.6);
        tl.to(stamp, { opacity: 1, scale: 1, duration: 0.25 }, 3.75);
      });
    },
    { scope: rootRef },
  );

  return (
    <Section id="how-proven" heading="Four checks stand between a file and your books.">
      <div ref={rootRef} className={styles.stage}>
        <div className={styles.steps}>
          <span className={styles.rule} aria-hidden="true">
            <span className={styles.ruleFill} data-fx="rule" />
          </span>
          <ol className={styles.list} aria-label="Pipeline stages">
            {TRAIL.map((id, i) => (
              <li key={id} className={styles.step} data-step={i}>
                <span className={styles.stepLabel}>
                  <span className={styles.stepNo}>{String(i + 1).padStart(2, "0")}</span>
                  <ScrambleLabel text={labelOf(id)} />
                </span>
                <p className={styles.question}>{QUESTION[id as Exclude<Stage, "validate">]}</p>
                <p className={styles.job}>{JOB[id as Exclude<Stage, "validate">]}</p>
              </li>
            ))}
          </ol>
        </div>

        <div className={styles.screen}>
          <p className="sr-only">
            Released statement: opening {RELEASED.opening} plus credits {RELEASED.creditTotal} minus debits{" "}
            {RELEASED.debitTotal} equals closing {RELEASED.closing}.
          </p>
          <div aria-hidden="true">
            <DeviceFrame variant="laptop">
              <LedgerScreen />
            </DeviceFrame>
          </div>
        </div>
      </div>

      <Reveal as="div" className={styles.checks} y={10}>
        <ProvenChecks />
      </Reveal>
    </Section>
  );
}
