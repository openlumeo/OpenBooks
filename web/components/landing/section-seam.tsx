'use client';
import { useRef } from 'react';
import { gsap, useGSAP, DESKTOP_MOTION, markMotionReady } from '@/components/motion/gsap-setup';
import styles from './section-seam.module.css';

export function SectionSeam() {
  const ref = useRef<SVGSVGElement>(null);
  useGSAP(() => {
    markMotionReady();
    const svg = ref.current;
    if (!svg) return;
    gsap.matchMedia().add(DESKTOP_MOTION, () => {
      gsap.from(svg.querySelectorAll('path'), {
        drawSVG: '0%', ease: 'none', stagger: 0.15,
        scrollTrigger: { trigger: svg, start: 'top 95%', end: 'top 60%', scrub: 0.5 },
      });
    });
  }, { scope: ref });
  return (
    <svg ref={ref} className={styles.seam} viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <path d="M0 1 H100" /><path d="M0 5 H100" />
    </svg>
  );
}
