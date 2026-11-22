/* docs: Scroll-in reveal. Final state is the default; JS adds motion.
 *   <Reveal as="div" delay={0} stagger={0.1} y={16} once>...</Reveal>
 *     Sets data-reveal on the wrapper. It animates opacity 0 -> 1 and y -> 0 when its top
 *     reaches 85% of the viewport (expo.out, 0.9s). Children marked data-reveal-child
 *     animate in sequence (stagger) instead of the wrapper.
 *   useReveal(scopeRef, opts)
 *     Animates every [data-reveal] inside scopeRef, for markup you do not wrap.
 * Times (delay, stagger) are seconds. y is px. The hidden state is CSS only
 * (motion.css, under html.lp-js and no-preference), so no JS means no hidden content. */
'use client';

import { useRef, type ElementType, type HTMLAttributes, type ReactNode, type RefObject } from 'react';
import { gsap, useGSAP, MOTION_OK, markMotionReady } from './gsap-setup';

export type RevealOptions = {
  delay?: number;
  stagger?: number;
  y?: number;
  once?: boolean;
};

type ResolvedRevealOptions = Required<RevealOptions>;

function playReveal(el: HTMLElement, o: ResolvedRevealOptions): void {
  const kids = gsap.utils.toArray<HTMLElement>(el.querySelectorAll('[data-reveal-child]'));
  const staggered = kids.length > 0;
  // The wrapper stays visible when children carry the hidden state.
  if (staggered) gsap.set(el, { opacity: 1, y: 0 });
  gsap.fromTo(
    staggered ? kids : [el],
    { opacity: 0, y: o.y },
    {
      opacity: 1,
      y: 0,
      duration: 0.9,
      ease: 'expo.out',
      delay: o.delay,
      stagger: staggered ? o.stagger : 0,
      scrollTrigger: {
        trigger: el,
        start: 'top 85%',
        once: o.once,
        ...(o.once ? {} : { toggleActions: 'play reverse play reverse' }),
      },
    },
  );
}

export type RevealProps = RevealOptions &
  HTMLAttributes<HTMLElement> & {
    as?: ElementType;
    children?: ReactNode;
  };

export function Reveal({
  as: Tag = 'div',
  delay = 0,
  stagger = 0.1,
  y = 16,
  once = true,
  children,
  ...rest
}: RevealProps) {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      markMotionReady();
      const el = ref.current;
      if (!el) return;
      gsap.matchMedia().add(MOTION_OK, () => playReveal(el, { delay, stagger, y, once }));
    },
    { scope: ref, dependencies: [delay, stagger, y, once] },
  );

  return (
    <Tag ref={ref} {...rest} data-reveal="">
      {children}
    </Tag>
  );
}

export function useReveal(scope: RefObject<HTMLElement | null>, options: RevealOptions = {}): void {
  const { delay = 0, stagger = 0.1, y = 16, once = true } = options;

  useGSAP(
    () => {
      markMotionReady();
      const root = scope.current;
      if (!root) return;
      gsap.matchMedia().add(MOTION_OK, () => {
        const blocks = gsap.utils.toArray<HTMLElement>('[data-reveal]', root);
        blocks.forEach((el) => playReveal(el, { delay, stagger, y, once }));
      });
    },
    { scope, dependencies: [delay, stagger, y, once] },
  );
}
