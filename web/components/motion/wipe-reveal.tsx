'use client';
import { useRef, type ReactNode } from 'react';
import { gsap, useGSAP, MOTION_OK, markMotionReady } from '@/components/motion/gsap-setup';

type WipeFrom = 'left' | 'top' | 'bottom';
const HIDDEN: Record<WipeFrom, string> = { left: 'inset(0 100% 0 0)', top: 'inset(0 0 100% 0)', bottom: 'inset(100% 0 0 0)' };
const SHOWN = 'inset(0 0 0 0)';

export function WipeReveal({ from = 'left', className, children }: { from?: WipeFrom; className?: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    markMotionReady();
    const el = ref.current;
    if (!el) return;
    gsap.matchMedia().add(MOTION_OK, () => {
      gsap.fromTo(el, { clipPath: HIDDEN[from] }, {
        clipPath: SHOWN, duration: 0.7, ease: 'power2.inOut', clearProps: 'clipPath',
        scrollTrigger: { trigger: el, start: 'top 85%', once: true },
      });
    });
  }, { scope: ref });
  return <div ref={ref} className={className}>{children}</div>;
}
