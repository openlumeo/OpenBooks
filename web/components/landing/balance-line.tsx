'use client';
import { useRef } from 'react';
import { gsap, useGSAP, MOTION_OK, markMotionReady } from '@/components/motion/gsap-setup';
import { RELEASED } from './proof-data';
import styles from './balance-line.module.css';

export function BalanceLine() {
  const ref = useRef<HTMLElement>(null);
  useGSAP(() => {
    markMotionReady();
    const root = ref.current;
    if (!root) return;
    gsap.matchMedia().add(MOTION_OK, () => buildBalance(root));
  }, { scope: ref });
  return (
    <figure ref={ref} className={styles.line}>
      <figcaption className={styles.caption}>
        {RELEASED.fileName} · {RELEASED.equationAssertion.id} {RELEASED.equationAssertion.rule}
      </figcaption>
      <p className={styles.eq}>
        <span data-term>{RELEASED.opening}</span> <span data-op>+</span>
        <span data-term>{RELEASED.creditTotal}</span> <span data-op>−</span>
        <span data-term>{RELEASED.debitTotal}</span> <span data-op>=</span>
        <span data-term className={styles.total}>
          {RELEASED.closing}
          <svg aria-hidden="true" focusable="false" viewBox="0 0 100 8" preserveAspectRatio="none" className={styles.rule}>
            <path d="M0 2 H100" />
            <path d="M0 6 H100" />
          </svg>
        </span>{' '}
        <span className={styles.currency}>{RELEASED.currency}</span>
      </p>
    </figure>
  );
}

function buildBalance(root: HTMLElement): void {
  const terms = root.querySelectorAll('[data-term]');
  const ops = root.querySelectorAll('[data-op]');
  gsap.timeline({ scrollTrigger: { trigger: root, start: 'top 80%', once: true } })
    .from(terms, { clipPath: 'inset(0 100% 0 0)', duration: 0.5, ease: 'power2.out', stagger: 0.18, clearProps: 'clipPath' })
    .from(ops, { opacity: 0, duration: 0.3, stagger: 0.18 }, 0.1);
}
