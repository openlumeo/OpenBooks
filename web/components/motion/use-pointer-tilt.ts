/* docs: usePointerTilt(ref, { max: 6 }) on an inner element inside a perspective parent.
 * Tilts rotateX/rotateY toward the pointer with gsap.quickTo (spring ease), resets on leave.
 * Mouse and pen only; off for reduced motion and coarse pointers. Listeners are removed on unmount.
 * Apply to an element that does not also carry a Reveal transform (use a child wrapper). */
'use client';

import { useEffect, type RefObject } from 'react';
import { gsap, FINE_POINTER_MOTION } from './gsap-setup';

export type PointerTiltOptions = { max?: number };

export function usePointerTilt(ref: RefObject<HTMLElement | null>, options: PointerTiltOptions = {}): void {
  const max = options.max ?? 6;

  useEffect(() => {
    const el = ref.current;
    if (!el || !window.matchMedia(FINE_POINTER_MOTION).matches) return;

    gsap.set(el, { transformPerspective: 900, transformOrigin: '50% 50%' });
    const ease = 'elastic.out(1, 0.6)';
    const setX = gsap.quickTo(el, 'rotateX', { duration: 0.9, ease });
    const setY = gsap.quickTo(el, 'rotateY', { duration: 0.9, ease });

    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse' && event.pointerType !== 'pen') return;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const px = (event.clientX - rect.left) / rect.width - 0.5;
      const py = (event.clientY - rect.top) / rect.height - 0.5;
      setY(px * 2 * max);
      setX(-py * 2 * max);
    };
    const onLeave = () => {
      setX(0);
      setY(0);
    };

    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    return () => {
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
      gsap.killTweensOf(el, 'rotateX,rotateY');
    };
  }, [ref, max]);
}
