'use client';
import type { RefObject } from 'react';
import { gsap, useGSAP, DESKTOP_FINE_MOTION, markMotionReady } from '@/components/motion/gsap-setup';

export function useHeroDepth(scope: RefObject<HTMLElement | null>): void {
  useGSAP(() => {
    markMotionReady();
    const root = scope.current;
    if (!root) return;
    gsap.matchMedia().add(DESKTOP_FINE_MOTION, () => {
      const area = root.closest<HTMLElement>('section') ?? root;
      const layers = gsap.utils.toArray<HTMLElement>('[data-depth]', root).map((el) => ({
        d: Number(el.dataset.depth) || 0,
        x: gsap.quickTo(el, 'xPercent', { duration: 1.2, ease: 'power3.out' }),
        y: gsap.quickTo(el, 'yPercent', { duration: 1.2, ease: 'power3.out' }),
      }));
      const onMove = (e: PointerEvent) => {
        if (e.pointerType !== 'mouse' && e.pointerType !== 'pen') return;
        const nx = e.clientX / window.innerWidth - 0.5;
        const ny = e.clientY / window.innerHeight - 0.5;
        layers.forEach((l) => { l.x(-nx * l.d); l.y(-ny * l.d); });
      };
      const onLeave = () => layers.forEach((l) => { l.x(0); l.y(0); });
      area.addEventListener('pointermove', onMove);
      area.addEventListener('pointerleave', onLeave);
      return () => {
        area.removeEventListener('pointermove', onMove);
        area.removeEventListener('pointerleave', onLeave);
      };
    });
  }, { scope });
}
