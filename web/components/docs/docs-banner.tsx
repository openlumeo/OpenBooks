import { Sketch } from "@/components/motion/sketch";

export function DocsBanner() {
  return (
    <div className="ob-banner" aria-hidden="true">
      <svg viewBox="0 0 480 160" focusable="false">
        <g fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6">
          <path className="ob-banner-ink" d="M120 18 C 200 12, 300 14, 364 17 C 368 60, 366 100, 368 146 C 300 150, 200 148, 118 146 C 122 104, 119 60, 120 18 Z" />
          <path className="ob-banner-ink" d="M136 40 H 350 M136 62 H 330 M136 84 H 344 M136 106 H 292" strokeWidth="1.2" />
          <path className="ob-banner-tick" d="M322 118 L 334 130 L 356 104" strokeWidth="2.2" />
          <path className="ob-banner-tick" d="M92 30 L 96 146 M104 22 L 106 152" strokeWidth="0.9" opacity="0.5" />
          <path className="ob-banner-tick" d="M400 34 C 430 30, 452 52, 446 78 C 440 104, 408 112, 396 90" strokeWidth="1.4" opacity="0.8" />
        </g>
      </svg>
      <Sketch kind="underline" tone="mint" />
    </div>
  );
}
