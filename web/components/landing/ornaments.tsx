// Original line-art objects for the landing page. Decorative only: all are aria-hidden.
type Props = { className?: string };

const base = { viewBox: "0 0 96 96", fill: "none", stroke: "currentColor", strokeWidth: 2.5, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true, focusable: false } as const;

/** Open ledger book. */
export function LedgerGlyph({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M48 24c-8-6-22-7-34-3v52c12-4 26-3 34 3 8-6 22-7 34-3V21c-12-4-26-3-34 3Z" />
      <path d="M48 24v52M22 34c6-1 14 0 20 3M22 46c6-1 14 0 20 3M54 37c6-3 14-4 20-3M54 49c6-3 14-4 20-3" />
    </svg>
  );
}

/** Balance scale: the "ties out" check. */
export function BalanceGlyph({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M48 14v62M30 80h36M20 28h56" />
      <path d="M20 28 8 54a12 8 0 0 0 24 0L20 28ZM76 28 64 54a12 8 0 0 0 24 0L76 28Z" />
    </svg>
  );
}

/** Wax seal with a check: the proven release. */
export function SealGlyph({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M48 10l8 6 10-1 4 9 9 4-1 10 6 8-6 8 1 10-9 4-4 9-10-1-8 6-8-6-10 1-4-9-9-4 1-10-6-8 6-8-1-10 9-4 4-9 10 1 8-6Z" />
      <path d="M33 49l11 11 20-22" />
    </svg>
  );
}

/** Magnifier over a page: format detection. */
export function DetectGlyph({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M22 10h34l16 16v22M22 10v70h26" />
      <path d="M56 10v16h16" />
      <circle cx="64" cy="66" r="13" />
      <path d="m74 76 12 12" />
    </svg>
  );
}

/** Doric column: the "built to last" stat block. */
export function ColumnGlyph({ className }: Props) {
  return (
    <svg {...base} viewBox="0 0 96 160" className={className}>
      <path d="M14 18h68M20 18c0-6 8-10 28-10s28 4 28 10M24 30h48M30 30v100M40 30v100M52 30v100M62 30v100M72 30v100M22 130h52M14 142h68M10 154h76" />
    </svg>
  );
}

/** Stacked blocks forming an arch, with a seal set on top: the closing illustration. */
export function ArchGlyph({ className }: Props) {
  return (
    <svg {...base} viewBox="0 0 320 200" className={className}>
      <path d="M10 190h300M10 190v-34h60v34M250 190v-34h60v34M70 156v-48h40v48M210 156v-48h40v48" />
      <path d="M70 108c0-48 40-72 90-72s90 24 90 72M110 108c0-28 22-44 50-44s50 16 50 44" />
      <path d="M130 36l16-16h28l16 16" />
      <circle cx="160" cy="14" r="12" />
      <path d="M154 14l5 5 8-9" />
    </svg>
  );
}

/** Rows and columns: parse + normalise. */
export function RowsGlyph({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <rect x="10" y="16" width="76" height="64" rx="6" />
      <path d="M10 36h76M10 52h76M10 66h76M38 16v64" />
    </svg>
  );
}
