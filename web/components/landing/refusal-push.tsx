'use client';
import { useRef, type ReactNode } from 'react';
import { gsap, useGSAP, DESKTOP_MOTION, markMotionReady } from '@/components/motion/gsap-setup';

const PUSH_DISTANCE = '+=70%';

/** Desktop only: pins the proof block and pushes the camera in on the engine's refusal message. */
export function RefusalPush({ className, children }: { className?: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    markMotionReady();
    const root = ref.current;
    if (!root) return;
    gsap.matchMedia().add(DESKTOP_MOTION, () => {
      const panel = root.querySelector<HTMLElement>('[data-push]');
      const caption = root.querySelector<HTMLElement>('[data-push-caption]');
      if (!panel) return;
      const fits = root.offsetHeight < window.innerHeight * 0.9; // never pin a block taller than the viewport
      const tl = gsap.timeline({
        defaults: { ease: 'none' },
        scrollTrigger: fits
          ? { trigger: root, start: 'center center', end: PUSH_DISTANCE, pin: true, anticipatePin: 1, scrub: 0.6, invalidateOnRefresh: true }
          : { trigger: root, start: 'top 80%', end: 'center center', scrub: 0.6 },
      });
      tl.fromTo(panel, { z: -280, rotationX: 10, opacity: 0.45 }, { z: 0, rotationX: 0, opacity: 1, duration: 1 }, 0);
      if (caption) tl.fromTo(caption, { opacity: 0 }, { opacity: 1, duration: 0.2 }, 0.8);
    });
  }, { scope: ref });
  return <div ref={ref} className={className}>{children}</div>;
}
