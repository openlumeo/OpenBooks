'use client';
import { useRef, type ElementType, type HTMLAttributes, type ReactNode } from 'react';
import { gsap, SplitText, useGSAP, MOTION_OK, markMotionReady } from '@/components/motion/gsap-setup';

export type LineRevealProps = HTMLAttributes<HTMLElement> & { as?: ElementType; children: ReactNode };

/** Heading whose lines rise out of a clip mask at 85% of the viewport. Static without motion. */
export function LineReveal({ as: Tag = 'h2', children, ...rest }: LineRevealProps) {
  const ref = useRef<HTMLElement>(null);
  useGSAP(
    () => {
      markMotionReady();
      const el = ref.current;
      if (!el) return;
      gsap.matchMedia().add(MOTION_OK, () => {
        const split = SplitText.create(el, {
          type: 'lines',
          mask: 'lines',
          linesClass: 'lp-line',
          autoSplit: true,
          onSplit: (self) =>
            gsap.from(self.lines, {
              yPercent: 110,
              duration: 0.9,
              ease: 'expo.out',
              stagger: 0.08,
              scrollTrigger: { trigger: el, start: 'top 85%', once: true },
            }),
        });
        return () => split.revert();
      });
    },
    { scope: ref },
  );
  return (
    <Tag ref={ref} {...rest}>
      {children}
    </Tag>
  );
}
