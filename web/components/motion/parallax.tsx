'use client';

import { useRef, type ElementType, type HTMLAttributes, type ReactNode } from 'react';
import { gsap, useGSAP, FINE_POINTER_MOTION, markMotionReady } from './gsap-setup';

export type ParallaxProps = HTMLAttributes<HTMLElement> & {
  speed?: number;
  as?: ElementType;
  children?: ReactNode;
};

export function Parallax({ speed = 8, as: Tag = 'div', children, ...rest }: ParallaxProps) {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      markMotionReady();
      const el = ref.current;
      if (!el) return;
      gsap.matchMedia().add(FINE_POINTER_MOTION, () => {
        gsap.fromTo(
          el,
          { yPercent: 0 },
          {
            yPercent: -speed,
            ease: 'none',
            scrollTrigger: {
              trigger: el,
              start: 'top bottom',
              end: 'bottom top',
              scrub: 0.6,
              onToggle: (self) => {
                el.style.willChange = self.isActive ? 'transform' : '';
              },
            },
          },
        );
      });
    },
    { scope: ref, dependencies: [speed] },
  );

  return (
    <Tag ref={ref} {...rest}>
      {children}
    </Tag>
  );
}

export type ParallaxLayerProps = Omit<ParallaxProps, 'speed'> & {
  depth?: 1 | 2 | 3;
  reverse?: boolean;
};

const DEPTH_SPEED = { 1: 4, 2: 8, 3: 12 } as const;

export function ParallaxLayer({ depth = 1, reverse = false, ...rest }: ParallaxLayerProps) {
  const magnitude = DEPTH_SPEED[depth];
  return <Parallax {...rest} speed={reverse ? -magnitude : magnitude} />;
}
