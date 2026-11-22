'use client';

import { useRef } from 'react';
import { gsap, useGSAP, DESKTOP_MOTION, MOBILE_MOTION, markMotionReady } from '@/components/motion/gsap-setup';
import { ENGINE_STAGES } from './proof-data';
import styles from './file-route.module.css';

const ROUTE_D = 'M20 60 C 180 10, 300 110, 420 60 S 700 10, 980 60';
const STATION_X = [200, 420, 640, 860] as const;
const STATION_Y = [54, 60, 22.5, 41] as const;
const STATION_PROGRESS = [0.18, 0.42, 0.66, 0.88] as const;
const CARRIER_REST = 'translate(980 60)';
const DOC_D = 'M-12 -15 H5 L12 -8 V15 H-12 Z M-6 0 H6 M-6 6 H6';
const STAMP_D =
  'M-10 -14 H10 Q14 -14 14 -10 V10 Q14 14 10 14 H-10 Q-14 14 -14 10 V-10 Q-14 -14 -10 -14 Z M-7 0 L-2 5 L8 -5';

function buildRoute(root: HTMLElement) {
  const carrier = root.querySelector<SVGGElement>('[data-carrier]');
  const glyph = root.querySelector<SVGPathElement>('[data-glyph]');
  const route = root.querySelector<SVGPathElement>('[data-route]');
  const ticks = gsap.utils.toArray<SVGPathElement>('[data-tick]', root);
  if (!carrier || !glyph || !route) return;

  carrier.removeAttribute('transform');
  gsap.set(glyph, { morphSVG: DOC_D });
  gsap.set(ticks, { drawSVG: '0%' });

  const timeline = gsap.timeline({
    defaults: { ease: 'none' },
    scrollTrigger: { trigger: root, start: 'top 85%', end: 'bottom 35%', scrub: 0.5 },
  });
  timeline.to(carrier, { motionPath: { path: route, align: route, alignOrigin: [0.5, 0.5] }, duration: 1 }, 0);
  ticks.forEach((tick, index) => {
    timeline.to(tick, { drawSVG: '100%', duration: 0.05 }, STATION_PROGRESS[index]);
  });
  timeline.to(glyph, { morphSVG: STAMP_D, duration: 0.08 }, 0.9);

  return () => {
    gsap.set(carrier, { clearProps: 'all' });
    carrier.setAttribute('transform', CARRIER_REST);
    glyph.setAttribute('d', STAMP_D);
  };
}

function buildMobile(root: HTMLElement) {
  gsap.from(root, {
    opacity: 0,
    y: 12,
    duration: 0.5,
    scrollTrigger: { trigger: root, start: 'top 85%', once: true },
  });
}

export function FileRoute() {
  const ref = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      markMotionReady();
      const root = ref.current;
      if (!root) return;
      const mm = gsap.matchMedia();
      mm.add(DESKTOP_MOTION, () => buildRoute(root));
      mm.add(MOBILE_MOTION, () => buildMobile(root));
    },
    { scope: ref },
  );

  return (
    <div ref={ref} className={styles.route} aria-hidden="true">
      <svg viewBox="0 0 1000 120" className={styles.svg} focusable="false">
        <path data-route d={ROUTE_D} className={styles.rule} />
        {ENGINE_STAGES.map((stage, index) => (
          <g key={stage} transform={`translate(${STATION_X[index]} ${STATION_Y[index]})`}>
            <circle r="10" className={styles.ring} />
            <path data-tick d="M-5 0 L-1 4 L6 -5" className={styles.tick} />
            <text y="34" textAnchor="middle" className={styles.label}>
              {stage}
            </text>
          </g>
        ))}
        <g data-carrier transform={CARRIER_REST}>
          <path data-glyph d={STAMP_D} className={styles.glyph} />
        </g>
      </svg>
    </div>
  );
}
