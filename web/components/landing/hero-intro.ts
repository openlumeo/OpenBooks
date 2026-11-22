'use client';
import type { RefObject } from 'react';
import { gsap, useGSAP, MOTION_OK, markMotionReady } from '@/components/motion/gsap-setup';

const STAMP_AT_S = 0.95;

export function useHeroIntro(scope: RefObject<HTMLElement | null>): void {
  useGSAP(() => {
    markMotionReady();
    const root = scope.current;
    if (!root || window.scrollY > 0) return;
    gsap.matchMedia().add(MOTION_OK, () => playIntro(root));
  }, { scope });
}

function playIntro(root: HTMLElement): void {
  const lines = root.querySelectorAll('[data-intro-line]');
  const sketchStamp = root.querySelector('[data-intro-stamp]');
  const stamp = root.querySelector('[data-hero-stamp]');
  const tl = gsap.timeline({ defaults: { ease: 'power2.out' } });
  tl.from(lines, { drawSVG: '0%', duration: 0.8, stagger: 0.05 }, 0.1);
  if (sketchStamp) tl.from(sketchStamp, { drawSVG: '0%', duration: 0.35 }, '>-0.2');
  if (stamp) tl.from(stamp, { scale: 1.35, rotation: -6, duration: 0.3, ease: 'power4.in', transformOrigin: '50% 50%' }, STAMP_AT_S);
}
