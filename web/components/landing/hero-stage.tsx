'use client';

// HeroStage: the stage under the hero copy. Owns the released/refused state, the bloom
// layers, the AlterSwitch and the one scroll scrub.
//
// Static first: the CSS pose is the finished composition (released, tilted 18deg, all
// rows tied, stamp landed). GSAP runs only under gsap.matchMedia for desktop (>= 900px)
// with motion allowed. There it pins the hero section for 120% of a viewport
// (ScrollTrigger, scrub 0.6, ease none) and flattens the monolith to rotateX 0 while it
// rises to the vertical centre, the back plane parallaxes, the lead lifts out, each tie
// bar retracts and redraws in turn, and the stamp takes one press at the end.
// The scrub touches transform only, never the stamp content or the state. The toggle
// morph belongs to HeroMonolith (CSS keyed to data-state). HeroMonolith carries its own
// perspective and 18deg tilt; the dock layer mirrors that perspective and tilt.
import { useRef, useState } from "react";
import { gsap, useGSAP, DESKTOP_MOTION, markMotionReady } from "@/components/motion/gsap-setup";
import { usePointerTilt } from "@/components/motion/use-pointer-tilt";
import { useHeroDepth } from "./hero-depth";
import { HeroMonolith } from "./hero-monolith";
import { AlterSwitch } from "./alter-switch";
import styles from "./hero-stage.module.css";

const PIN_DISTANCE = "+=120%";
const TILT_DEG = 18;
const LEAD_CLEARANCE_PX = 48;

const REFUSED_NOTICE = "Refused. BALANCE_MISMATCH, running balance does not tie.";
const RELEASED_NOTICE = "Released. Opening plus transactions equals closing.";

/** Distance from el's top to ancestor's top, summed over offsetParent steps (ignores transforms). */
function offsetWithin(el: HTMLElement, ancestor: HTMLElement): number {
  let y = 0;
  let node: HTMLElement | null = el;
  while (node && node !== ancestor) {
    y += node.offsetTop;
    node = node.offsetParent as HTMLElement | null;
  }
  return y;
}

/** Decorative hand-sketched ledger page with a stamp outline. Meaning lives in the monolith text. */
function LedgerSketch() {
  const rules = [60, 96, 132, 168, 204, 240, 276, 312];
  return (
    <svg
      className={styles.ledgerSketch}
      data-depth="1.5"
      viewBox="0 0 240 340"
      aria-hidden="true"
      focusable="false"
    >
      <path className={styles.ledgerPage} d="M14 10 C 80 6, 160 8, 228 12 C 231 120, 229 230, 232 326 C 160 330, 80 328, 10 331 C 12 240, 9 120, 14 10 Z" />
      <path className={styles.ledgerMargin} d="M46 16 C 46 120, 47 240, 46 324 M50 16 C 50 120, 51 240, 50 324" />
      {rules.map((y) => (
        <path key={y} className={styles.ledgerRule} d={`M56 ${y} C 110 ${y - 2}, 170 ${y + 2}, 224 ${y}`} />
      ))}
      <path className={styles.ledgerStamp} d="M88 250 C 120 246, 160 247, 188 251 C 191 266, 189 282, 190 296 C 160 300, 120 298, 86 297 C 85 282, 88 266, 88 250 Z" />
    </svg>
  );
}

export function HeroStage() {
  const [altered, setAltered] = useState(false);
  // Empty on first render, so the live region only speaks after a toggle.
  const [notice, setNotice] = useState("");
  const scope = useRef<HTMLDivElement>(null);
  const tiltRef = useRef<HTMLDivElement>(null);
  usePointerTilt(tiltRef, { max: 3 });
  useHeroDepth(scope);

  useGSAP(
    () => {
      markMotionReady();
      const root = scope.current;
      if (!root) return;
      const hero = root.closest<HTMLElement>("section") ?? root;

      gsap.matchMedia().add(DESKTOP_MOTION,() => {
        const lead = hero.querySelector<HTMLElement>("[data-hero-lead]");
        const instrument = root.querySelector<HTMLElement>('[data-hero-plane="instrument"]');
        const dock = root.querySelector<HTMLElement>("[data-hero-dock]");
        const back = root.querySelector<HTMLElement>('[data-hero-plane="back"]');
        // The stamp and the verdict plate share one slot. Pressing the slot keeps the
        // stamp's own transform (its rotation and the refused offset) untouched.
        const slot = root.querySelector<HTMLElement>("[data-hero-stamp]")?.parentElement ?? null;
        const bars = gsap.utils.toArray<HTMLElement>(root.querySelectorAll("[data-hero-tie]"));
        if (!lead || !instrument || !dock) return;

        // Measured when the trigger refreshes (invalidateOnRefresh), so resize stays correct.
        const measure = () => {
          const vh = hero.clientHeight;
          const height = instrument.offsetHeight;
          const restTop = offsetWithin(instrument, hero);
          return {
            ty: (vh - height) / 2 - restTop,
            ly: -(lead.offsetTop + lead.offsetHeight + LEAD_CLEARANCE_PX),
          };
        };

        // The monolith tilts its own plane (CSS, 18deg). The dock layer carries the same tilt
        // so the switch stays on the instrument's top edge while it flattens and rises.
        gsap.set([instrument, dock], { rotationX: TILT_DEG, transformOrigin: "50% 100%" });
        if (back) gsap.set(back, { z: -200, rotationX: TILT_DEG, transformOrigin: "50% 100%" });
        bars.forEach((bar) => gsap.set(bar, { transformOrigin: "50% 0%" }));

        const tl = gsap.timeline({
          defaults: { ease: "none" },
          scrollTrigger: {
            trigger: hero,
            start: "top top",
            end: PIN_DISTANCE,
            pin: true,
            anticipatePin: 1,
            invalidateOnRefresh: true,
            scrub: 0.6,
          },
        });

        // 0.00-0.70: the monolith flattens and rises to the vertical centre (dock with it).
        tl.to([instrument, dock], { rotationX: 0, y: () => measure().ty, duration: 0.7 }, 0);
        // 0.00-1.00: the back plane moves at about 0.4x the front travel.
        if (back) tl.to(back, { y: () => 0.4 * measure().ty, duration: 1 }, 0);
        // 0.00-1.00: the sketch scrolls at 0.6x the front travel (y only; pointer parallax uses xPercent/yPercent).
        const sketch = root.querySelector<HTMLElement>("svg[data-depth]");
        if (sketch) tl.to(sketch, { y: () => 0.6 * measure().ty, duration: 1 }, 0);
        // 0.00-0.50: headline, lede and actions lift out of the viewport.
        tl.to(lead, { y: () => measure().ly, duration: 0.5 }, 0);
        // 0.30-0.84: each tie bar retracts and redraws in turn; the end state is all tied.
        bars.forEach((bar, i) => {
          const s = 0.3 + i * 0.11;
          tl.to(bar, { scaleY: 0, duration: 0.05 }, s);
          tl.to(bar, { scaleY: 1, duration: 0.05 }, s + 0.05);
        });
        // 0.90-1.00: the stamp slot lands with one press. The inline transform is cleared at the
        // end, so nothing overrides the CSS state of HeroMonolith.
        if (slot) {
          tl.to(slot, { scale: 0.94, duration: 0.04 }, 0.9);
          tl.to(slot, { scale: 1, duration: 0.06 }, 0.94);
          tl.set(slot, { clearProps: "transform" }, 1);
        }
      });
    },
    { scope },
  );

  const handleChange = (next: boolean) => {
    setAltered(next);
    setNotice(next ? REFUSED_NOTICE : RELEASED_NOTICE);
  };

  return (
    <div ref={scope} className={styles.stage}>
      <div aria-hidden="true" data-depth="0.4" className={styles.atmos} />
      <div aria-hidden="true" data-depth="0.8" className={styles.bloom} />
      <div aria-hidden="true" className={styles.grain} />
      <LedgerSketch />

      <div className={styles.rise}>
        <div ref={tiltRef} className={styles.tilt}>
          <div className={styles.perspective}>
            <HeroMonolith state={altered ? "refused" : "released"} />
            <div data-hero-dock className={styles.dockLayer}>
              <AlterSwitch className={styles.dock} checked={altered} onChange={handleChange} />
            </div>
          </div>
        </div>
      </div>

      <p aria-live="polite" className={styles.visuallyHidden}>
        {notice}
      </p>
    </div>
  );
}
