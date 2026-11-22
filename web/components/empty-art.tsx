export function EmptyArt() {
  return (
    <svg className="ob-empty-art" viewBox="0 0 220 168" aria-hidden="true" focusable="false">
      <g className="ob-art-files" fill="var(--surface-2)" stroke="var(--hairline)" strokeWidth="1.2" strokeLinejoin="round">
        <path d="M118 22 L170 19 L178 96 L124 100 Z" opacity="0.55" />
        <path d="M112 14 L168 12 L174 90 L118 93 Z" opacity="0.8" />
        <path d="M106 8 L160 6 L166 84 L112 87 Z" />
        <path d="M108 8 L121 6 L120 20 L110 22" fill="none" stroke="var(--text-faint)" />
        <path d="M117 34 L150 33 M116 44 L156 43 M115 54 L152 53 M115 64 L146 63" fill="none" stroke="var(--hairline)" strokeDasharray="1 0" />
      </g>

      <g className="ob-art-ledger" fill="var(--surface)" stroke="var(--text-muted)" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round">
        <path d="M14 58 C 40 48, 72 47, 102 56 L 102 150 C 72 141, 40 142, 14 151 Z" />
        <path d="M102 56 C 130 47, 160 48, 186 58 L 186 151 C 160 142, 130 141, 102 150 Z" />
        <path d="M22 74 C 44 68, 70 68, 94 74 M22 90 C 44 84, 70 84, 94 90 M22 106 C 44 100, 70 100, 94 106 M22 122 C 44 116, 70 116, 94 122" fill="none" stroke="var(--hairline)" strokeWidth="1" />
        <path d="M110 74 C 132 68, 158 68, 180 74 M110 90 C 132 84, 158 84, 180 90 M110 106 C 132 100, 158 100, 180 106 M110 122 C 132 116, 158 116, 180 122" fill="none" stroke="var(--hairline)" strokeWidth="1" />
        <path d="M116 142 L 176 142" fill="none" stroke="var(--accent)" strokeWidth="1.6" />
        <path d="M150 128 L 158 136 L 176 118" fill="none" stroke="var(--accent)" strokeWidth="1.8" />
      </g>
    </svg>
  );
}
