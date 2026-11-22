'use client';
import { useRef } from 'react';
import { gsap, useGSAP, DESKTOP_FINE_MOTION, markMotionReady } from '@/components/motion/gsap-setup';
import styles from './follow-cursor.module.css';

const ACTIONABLE = 'a[href], button:not([disabled]), [role="button"], summary, label[for], input, select, textarea';
const MAGNETIC = '.btn-hero-primary, .btn-primary-landing';
const MAGNET_PULL = 0.25;
const MAGNET_MAX_PX = 8;

export function FollowCursor() {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    markMotionReady();
    const ring = ref.current;
    if (!ring) return;
    gsap.matchMedia().add(DESKTOP_FINE_MOTION, () => {
      const stopFollowing = followPointer(ring);
      const stopMagnets = bindMagnets();
      return () => {
        stopFollowing();
        stopMagnets();
      };
    });
  }, { scope: ref });
  return <div ref={ref} className={styles.ring} aria-hidden="true" />;
}

function followPointer(ring: HTMLDivElement): () => void {
  gsap.set(ring, { xPercent: -50, yPercent: -50 });
  const xTo = gsap.quickTo(ring, 'x', { duration: 0.45, ease: 'power3' });
  const yTo = gsap.quickTo(ring, 'y', { duration: 0.45, ease: 'power3' });
  const page = document.documentElement;
  let shown = false;
  const onMove = (e: PointerEvent) => {
    if (e.pointerType !== 'mouse') return;
    if (shown) {
      xTo(e.clientX);
      yTo(e.clientY);
    } else {
      xTo(e.clientX, e.clientX);
      yTo(e.clientY, e.clientY);
      shown = true;
      ring.dataset.visible = 'true';
    }
    ring.dataset.active = e.target instanceof Element && e.target.closest(ACTIONABLE) ? 'true' : 'false';
  };
  const onLeave = () => {
    shown = false;
    ring.dataset.visible = 'false';
  };
  window.addEventListener('pointermove', onMove, { passive: true });
  page.addEventListener('pointerleave', onLeave);
  return () => {
    window.removeEventListener('pointermove', onMove);
    page.removeEventListener('pointerleave', onLeave);
    delete ring.dataset.visible;
    delete ring.dataset.active;
  };
}

function bindMagnets(): () => void {
  const clamp = gsap.utils.clamp(-MAGNET_MAX_PX, MAGNET_MAX_PX);
  const stops = Array.from(document.querySelectorAll<HTMLElement>(MAGNETIC)).map((el) => {
    el.dataset.magnetic = 'true';
    const xTo = gsap.quickTo(el, 'x', { duration: 0.35, ease: 'power3' });
    const yTo = gsap.quickTo(el, 'y', { duration: 0.35, ease: 'power3' });
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse') return;
      const r = el.getBoundingClientRect();
      xTo(clamp((e.clientX - (r.left + r.width / 2)) * MAGNET_PULL));
      yTo(clamp((e.clientY - (r.top + r.height / 2)) * MAGNET_PULL));
    };
    const onLeave = () => {
      xTo(0);
      yTo(0);
    };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    return () => {
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
      delete el.dataset.magnetic;
      gsap.set(el, { clearProps: 'transform' });
    };
  });
  return () => stops.forEach((stop) => stop());
}
