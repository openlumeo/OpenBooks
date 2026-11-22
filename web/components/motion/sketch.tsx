'use client';

import { useRef, type ReactNode } from 'react';
import { gsap, useGSAP, MOTION_OK, markMotionReady } from './gsap-setup';
import styles from './sketch.module.css';

export type SketchKind = 'underline' | 'circle' | 'arrow' | 'bracket' | 'tick' | 'scribble' | 'stamp' | 'ledger-rule';
export type SketchTone = 'mint' | 'muted' | 'rose';

type SketchSpec = { viewBox: string; preserveAspectRatio: string; paths: string[] };

const SKETCHES: Record<SketchKind, SketchSpec> = {
  underline: {
    viewBox: '0 0 200 24',
    preserveAspectRatio: 'none',
    paths: ['M3 14 C 40 8, 92 20, 130 13 C 158 8, 180 9, 199 12'],
  },
  circle: {
    viewBox: '0 0 128 66',
    preserveAspectRatio: 'xMidYMid meet',
    paths: ['M100 14 C 66 0, 6 14, 10 34 C 14 54, 84 62, 110 40 C 124 24, 96 2, 44 10'],
  },
  arrow: {
    viewBox: '0 0 120 40',
    preserveAspectRatio: 'xMidYMid meet',
    paths: [
      'M6 30 C 36 24, 70 14, 110 12',
      'M110 12 C 101 12, 94 15, 89 21',
      'M110 12 C 107 19, 103 25, 97 31',
    ],
  },
  bracket: {
    viewBox: '0 0 20 120',
    preserveAspectRatio: 'none',
    paths: ['M14 3 C 6 4, 5 9, 5 18 C 5 50, 5 70, 5 102 C 5 111, 6 116, 14 117'],
  },
  tick: {
    viewBox: '0 0 24 24',
    preserveAspectRatio: 'xMidYMid meet',
    paths: ['M3 13 C 6 14, 9 18, 10 20 C 13 13, 18 6, 22 3'],
  },
  scribble: {
    viewBox: '0 0 200 30',
    preserveAspectRatio: 'none',
    paths: ['M3 18 C 20 6, 30 26, 48 14 C 64 4, 76 24, 94 14 C 110 4, 122 24, 140 14 C 156 5, 168 22, 197 11'],
  },
  stamp: {
    viewBox: '0 0 160 56',
    preserveAspectRatio: 'none',
    paths: [
      'M6 8 C 60 4, 110 6, 154 5 C 157 20, 155 36, 156 50 C 110 53, 60 51, 5 52 C 4 36, 7 22, 6 8 Z',
      'M11 13 C 60 11, 105 12, 149 11 C 151 24, 150 36, 151 45 C 105 47, 60 46, 10 47 C 9 36, 12 24, 11 13 Z',
    ],
  },
  'ledger-rule': {
    viewBox: '0 0 400 12',
    preserveAspectRatio: 'none',
    paths: ['M0 3 C 100 2, 300 4, 400 3', 'M0 9 C 120 8.5, 260 9.5, 400 9'],
  },
};

function cx(...names: Array<string | false | null | undefined>): string {
  return names.filter(Boolean).join(' ');
}

export type SketchProps = {
  kind: SketchKind;
  tone?: SketchTone;
  className?: string;
  start?: string;
  triggerSelector?: string;
};

export function Sketch({ kind, tone = 'mint', className, start = 'top 80%', triggerSelector }: SketchProps) {
  const ref = useRef<SVGSVGElement>(null);
  const spec = SKETCHES[kind];

  useGSAP(
    () => {
      markMotionReady();
      const svg = ref.current;
      if (!svg) return;
      const paths = gsap.utils.toArray<SVGPathElement>('path', svg);
      gsap.matchMedia().add(MOTION_OK, () => {
        gsap.fromTo(
          paths,
          { drawSVG: '0% 0%' },
          {
            drawSVG: '0% 100%',
            duration: 0.9,
            ease: 'power2.out',
            scrollTrigger: { trigger: (triggerSelector && svg.closest(triggerSelector)) || svg, start, once: true },
          },
        );
      });
    },
    { scope: ref, dependencies: [kind, start, triggerSelector] },
  );

  return (
    <svg
      ref={ref}
      viewBox={spec.viewBox}
      preserveAspectRatio={spec.preserveAspectRatio}
      aria-hidden="true"
      focusable="false"
      className={cx(styles.sketch, styles[tone], className)}
    >
      {spec.paths.map((d) => (
        <path key={d} d={d} vectorEffect="non-scaling-stroke" />
      ))}
    </svg>
  );
}

const OVERLAY_CLASS: Record<SketchKind, string | undefined> = {
  underline: styles['at-underline'],
  circle: styles['at-circle'],
  arrow: styles['at-arrow'],
  bracket: styles['at-bracket'],
  tick: styles['at-tick'],
  scribble: styles['at-scribble'],
  stamp: styles['at-stamp'],
  'ledger-rule': undefined,
};

export type SketchAnnotationProps = {
  kind: SketchKind;
  tone?: SketchTone;
  note?: string;
  className?: string;
  start?: string;
  triggerSelector?: string;
  children: ReactNode;
};

export function SketchAnnotation({ kind, tone = 'mint', note, className, start, triggerSelector, children }: SketchAnnotationProps) {
  return (
    <span className={cx(styles.anchor, className)}>
      {children}
      <Sketch kind={kind} tone={tone} className={OVERLAY_CLASS[kind]} start={start} triggerSelector={triggerSelector} />
      {note ? <span className={styles.note}>{note}</span> : null}
    </span>
  );
}
