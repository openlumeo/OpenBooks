'use client';

import { useRef } from 'react';
import { gsap, ScrollTrigger, useGSAP, DESKTOP_MOTION, markMotionReady } from '@/components/motion/gsap-setup';
import { INPUT_GROUPS } from './inputs-data';
import styles from './format-marquee.module.css';

const LAYOUT_IDS = INPUT_GROUPS.flatMap((group) => group.layouts);
const LOOP_SECONDS = 60;
const MAX_SPEED_BOOST = 4;
const VELOCITY_PER_BOOST = 600;
const MAX_SKEW_DEG = 6;
const SKEW_PER_VELOCITY = 300;
const SETTLE_DELAY_SECONDS = 0.15;

function buildMarquee(root: HTMLElement) {
  const track = root.querySelector<HTMLElement>('[data-track]');
  if (!track) return;

  root.dataset.running = 'true';
  const loop = gsap.to(track, { xPercent: -50, duration: LOOP_SECONDS, ease: 'none', repeat: -1, paused: true });
  const skewTo = gsap.quickTo(track, 'skewX', { duration: 0.4, ease: 'power3' });
  const settle = gsap.delayedCall(SETTLE_DELAY_SECONDS, () => {
    gsap.to(loop, { timeScale: 1, duration: 0.8 });
    skewTo(0);
  }).pause();

  const trigger = ScrollTrigger.create({
    trigger: root,
    start: 'top bottom',
    end: 'bottom top',
    onToggle: (self) => (self.isActive ? loop.play() : loop.pause()),
    onUpdate: (self) => {
      const velocity = self.getVelocity();
      const boost = Math.min(MAX_SPEED_BOOST, Math.abs(velocity) / VELOCITY_PER_BOOST);
      gsap.to(loop, { timeScale: 1 + boost, duration: 0.2, overwrite: true });
      skewTo(gsap.utils.clamp(-MAX_SKEW_DEG, MAX_SKEW_DEG, velocity / -SKEW_PER_VELOCITY));
      settle.restart(true);
    },
  });

  return () => {
    delete root.dataset.running;
    trigger.kill();
    settle.kill();
  };
}

export function FormatMarquee() {
  const ref = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      markMotionReady();
      const root = ref.current;
      if (!root) return;
      gsap.matchMedia().add(DESKTOP_MOTION, () => buildMarquee(root));
    },
    { scope: ref },
  );

  return (
    <div ref={ref} className={styles.marquee} aria-hidden="true">
      <div data-track className={styles.track}>
        <ul className={styles.list}>
          {LAYOUT_IDS.map((id) => (
            <li key={id}>{id}</li>
          ))}
        </ul>
        <ul className={styles.list} data-dup>
          {LAYOUT_IDS.map((id) => (
            <li key={`dup-${id}`}>{id}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
