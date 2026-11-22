"use client";

import { useRef } from "react";
import { gsap, useGSAP, MOTION_OK, markMotionReady } from "@/components/motion/gsap-setup";
import styles from "./trace.module.css";

/** Margin rule drawn down the transaction fields; it ends on Balance after with a mint dot. */
export function TraceLine() {
  const ref = useRef<HTMLSpanElement>(null);

  useGSAP(
    () => {
      markMotionReady();
      const root = ref.current;
      const row = root?.parentElement;
      if (!root || !row) return;

      gsap.matchMedia().add(MOTION_OK, () => {
        const path = root.querySelector("path");
        const dot = root.querySelector<HTMLElement>("[data-trace-dot]");
        const tl = gsap.timeline({
          defaults: { ease: "none" },
          scrollTrigger: { trigger: row, start: "top 75%", end: "bottom 55%", scrub: 0.6 },
        });
        if (path) tl.fromTo(path, { drawSVG: "0%" }, { drawSVG: "100%", duration: 0.9 }, 0);
        if (dot) tl.fromTo(dot, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.1 }, 0.9);
      });
    },
    { scope: ref },
  );

  return (
    <span ref={ref} aria-hidden="true" className={styles.traceLine}>
      <svg viewBox="0 0 8 100" preserveAspectRatio="none" focusable="false" aria-hidden="true">
        <path d="M4 0 C 2 30, 6 62, 4 100" fill="none" vectorEffect="non-scaling-stroke" />
      </svg>
      <span data-trace-dot="" className={styles.traceDot} />
    </span>
  );
}
