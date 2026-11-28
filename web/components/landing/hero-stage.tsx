'use client';

import { useEffect, useRef, useState } from "react";
import { gsap, useGSAP, DESKTOP_MOTION, markMotionReady } from "@/components/motion/gsap-setup";
import { useHeroDepth } from "./hero-depth";
import { DeviceFrame } from "./device-frame";
import styles from "./hero-stage.module.css";

const PIN_DISTANCE = "+=120%";
const TILT_DEG = 18;
const START_SCALE = 0.92;
const LEAD_CLEARANCE_PX = 48;
// Timeline progress at which the laptop counts as settled and the screen video may start.
const SETTLED_AT = 0.62;

function offsetWithin(el: HTMLElement, ancestor: HTMLElement): number {
  let y = 0;
  let node: HTMLElement | null = el;
  while (node && node !== ancestor) {
    y += node.offsetTop;
    node = node.offsetParent as HTMLElement | null;
  }
  return y;
}

const VIDEO_DESCRIPTION =
  "Screen recording of Open Books on a laptop: a statement.csv file is dragged into the workspace, the engine ticks detect, parse, normalise and balance, ledger rows tie to the equation 1000.00 + 6857.26 - 2756.86 = 5100.40 INR, and the result is stamped RELEASED with a Download JSON option.";

const POSTER_AT = 12.9;

function useActiveTheme(): "light" | "dark" {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  useEffect(() => {
    const root = document.documentElement;
    const read = () => setTheme(root.getAttribute("data-theme") === "light" ? "light" : "dark");
    read();
    const mo = new MutationObserver(read);
    mo.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
  }, []);
  return theme;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const read = () => setReduced(mq.matches);
    read();
    mq.addEventListener("change", read);
    return () => mq.removeEventListener("change", read);
  }, []);
  return reduced;
}

function HeroVideo({ play }: { play: boolean }) {
  const theme = useActiveTheme();
  const reduced = usePrefersReducedMotion();
  const dark = useRef<HTMLVideoElement>(null);
  const light = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const active = theme === "light" ? light.current : dark.current;
    const idle = theme === "light" ? dark.current : light.current;
    idle?.pause();
    if (!active) return;
    if (reduced) {
      // Reduced motion: hold the RELEASED frame (same moment as the poster), never autoplay.
      active.pause();
      const hold = () => {
        active.currentTime = POSTER_AT;
      };
      if (active.readyState >= 1) hold();
      else active.addEventListener("loadedmetadata", hold, { once: true });
      return () => active.removeEventListener("loadedmetadata", hold);
    }
    if (!play) {
      active.pause();
      return;
    }
    active.play().catch(() => undefined);
  }, [theme, play, reduced]);

  const sources = (name: "dark" | "light") => (
    <>
      <source src={`/motion/hero-workspace-${name}.webm`} type="video/webm" />
      <source src={`/motion/hero-workspace-${name}.mp4`} type="video/mp4" />
    </>
  );

  return (
    <>
      <video
        ref={dark}
        className={`${styles.video} ${styles.videoDark}`}
        muted
        loop
        playsInline
        preload="metadata"
        aria-hidden="true"
        tabIndex={-1}
        poster="/motion/hero-workspace-dark-poster.jpg"
      >
        {sources("dark")}
      </video>
      <video
        ref={light}
        className={`${styles.video} ${styles.videoLight}`}
        muted
        loop
        playsInline
        preload="metadata"
        aria-hidden="true"
        tabIndex={-1}
        poster="/motion/hero-workspace-light-poster.jpg"
      >
        {sources("light")}
      </video>
      <p className={styles.sr}>{VIDEO_DESCRIPTION}</p>
    </>
  );
}

export function HeroStage() {
  // On desktop the video waits until the laptop has risen; everywhere else it starts when in view.
  const [playGate, setPlayGate] = useState(true);
  const scope = useRef<HTMLDivElement>(null);
  useHeroDepth(scope);

  useGSAP(
    () => {
      markMotionReady();
      const root = scope.current;
      if (!root) return;
      const hero = root.closest<HTMLElement>("section") ?? root;

      gsap.matchMedia().add(DESKTOP_MOTION, () => {
        const lead = hero.querySelector<HTMLElement>("[data-hero-lead]");
        const laptop = root.querySelector<HTMLElement>('[data-hero-plane="instrument"]');
        const back = root.querySelector<HTMLElement>('[data-hero-plane="back"]');
        if (!lead || !laptop) return;

        setPlayGate(false);

        const measure = () => {
          const vh = hero.clientHeight;
          const height = laptop.offsetHeight;
          const restTop = offsetWithin(laptop, hero);
          return {
            ty: (vh - height) / 2 - restTop,
            ly: -(lead.offsetTop + lead.offsetHeight + LEAD_CLEARANCE_PX),
          };
        };

        gsap.set(laptop, { rotationX: TILT_DEG, scale: START_SCALE, transformOrigin: "50% 100%" });
        if (back) gsap.set(back, { y: 0 });

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
            onUpdate: (self) => {
              if (self.progress >= SETTLED_AT) setPlayGate(true);
            },
          },
        });

        tl.to(laptop, { rotationX: 0, scale: 1, y: () => measure().ty, duration: 0.7 }, 0);
        if (back) tl.to(back, { y: () => 0.4 * measure().ty, duration: 1 }, 0);
        tl.to(lead, { y: () => measure().ly, duration: 0.5 }, 0);
        // Hold the settled laptop for the rest of the pin.
        tl.to({}, { duration: 0.3 }, 0.7);

        return () => setPlayGate(true);
      });
    },
    { scope },
  );

  return (
    <div ref={scope} className={styles.stage}>
      <div aria-hidden="true" data-depth="0.4" className={styles.atmos} />
      <div aria-hidden="true" data-depth="0.8" className={styles.bloom} />
      <div aria-hidden="true" className={styles.grain} />

      <div className={styles.rise}>
        <div className={styles.perspective}>
          <div data-hero-plane="instrument" className={styles.laptop} role="group" aria-label="Open Books workspace">
            <DeviceFrame>
              <HeroVideo play={playGate} />
            </DeviceFrame>
          </div>
        </div>
      </div>
    </div>
  );
}
