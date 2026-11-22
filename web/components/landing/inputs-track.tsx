'use client';
import { useRef, type ReactNode } from 'react';
import { gsap, useGSAP, DESKTOP_MOTION, markMotionReady } from '@/components/motion/gsap-setup';
import styles from './inputs.module.css';

export function InputsTrack({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      markMotionReady();
      const viewport = ref.current;
      const track = viewport?.firstElementChild as HTMLElement | null;
      const section = viewport?.closest<HTMLElement>('section');
      if (!viewport || !track || !section) return;
      gsap.matchMedia().add(DESKTOP_MOTION, () => {
        const distance = () => Math.max(0, track.scrollWidth - viewport.clientWidth);
        if (distance() === 0 || section.offsetHeight > window.innerHeight) return;
        viewport.dataset.pinned = 'true';
        gsap.to(track, {
          x: () => -distance(),
          ease: 'none',
          scrollTrigger: {
            trigger: section,
            start: 'top top',
            end: () => '+=' + distance(),
            pin: true,
            anticipatePin: 1,
            scrub: 0.6,
            invalidateOnRefresh: true,
          },
        });
        return () => {
          delete viewport.dataset.pinned;
        };
      });
    },
    { scope: ref },
  );
  return (
    <div ref={ref} className={styles.viewport} role="region" aria-label="Accepted input formats" tabIndex={0}>
      {children}
    </div>
  );
}
