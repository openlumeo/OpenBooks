# Concept C, "The Equation" (port 5053)

**Idea.** The document's own arithmetic is the headline. One line, `1000.00 + 6857.26 - 2756.86 = 5100.40`, is the hero object; the H1 is smaller and sits above it. The lavender RELEASED stamp is the only lavender in the viewport.

**What the visitor sees.** Nav glass pill; H1 (2 lines); the equation in Geist Mono with the closing figure in Geist Sans at 1.5x; a mint equals rule under the terms; a muted mono legend `OPENING · CREDITS · DEBITS · CLOSING` under their terms; lede (2 lines); primary `Open workspace` and text link `Read the docs`. Faint ledger grid, plum bloom bottom right, hairlines only.

**Does.** Hover or keyboard-focus any term: the others step back, that figure turns mint, and a mono tooltip lists 1 to 2 real rows (for example `ROW 4 · CR · 494.51 · BAL 741.54`) with "3 of 8 rows not shown here". All values come from `proof-data.ts`.

**Motion timeline (about 5 s, one pass).**
- 0.0 nav fades; 0.1 H1 rises.
- 0.4 opening: source chip `STATEMENT · OPENING`, then the figure digit-rolls (0.9 to 1.4); `+` at 1.4.
- 1.4 credits: chip `ROWS 1-8 · CR`, roll 1.9 to 2.4; `-` at 2.4.
- 2.5 debits: chip `ROWS 1-8 · DR`, roll 3.0 to 3.5; `=` at 3.4.
- 3.4 mint rule draws left to right (to 4.0).
- 3.8 closing: chip, then the Geist figure rolls last (4.3 to 4.8).
- 4.9 RELEASED stamp lands (scale 1.35 to 1, rotated 2deg); legend fades in at 3.7; lede and CTAs rise at 5.0.

**Keyboard and semantics.** Each term is a `tabindex=0` span with `aria-describedby` pointing at its `role="tooltip"`. Focus shows the same state as hover, with a 2px accent outline. Tooltips are CSS-driven, so they work without JS. Touch devices open them on tap focus.

**Degradation.** No JS: the static frame is the fully resolved equation with the stamp and rule (checked: all figures final, stamp opacity 1). Reduced motion: the GSAP timeline is skipped and the same frame shows. An inline head script adds `.pre` (which hides content) only when motion is allowed; JS removes it, with a 2.5 s failsafe.

**Mobile (390).** Terms stack as a right-aligned ledger column with `+` and `-` in a left gutter, the mint equals rule between debits and closing, `=` before the closing figure, the stamp under it, and the legend as one line.

**Fit.** Figure size uses container units (`4.4cqi`) against the 1280px content box, so the equation is 1232px wide at 1440 and 1920 with no horizontal overflow. Verified: `scrollWidth` equals the viewport at 1440, 1920 and 390.

**Deviations (on purpose).** Lede sits under the equation, as this concept specifies, not directly under the H1. Lede trimmed to two lines: "...you get sourced, structured data. If not, the reason, never a guess." (trim allowed by the brief). Brand mark is the PNG with "Open Books / by Lumeo" set in HTML, because the lockup PNG carries a "lumeo" wordmark.

**Build in the Next.js site.**
- Replace the figures in `web/components/landing/hero.tsx` with an equation component fed by `RELEASED` in `proof-data.ts` (strings as-is, no number conversion).
- Style with a CSS module (`hero.module.css`) using `cqi` sizing; reuse `.t-display`, `.btn-primary-landing`, `.btn-secondary-landing`, the nav module, and the `.recon-stamp` treatment.
- Timeline: GSAP in `web/components/motion/*`, built inside `gsap.context()` and reverted on unmount; skip when `prefers-reduced-motion`. Digit roll is a small helper in the same motion folder. Lenis is not needed in this hero.
- Tooltip rows derive from `RELEASED.rows` (rows 1 to 8, five shown, `hiddenRowCount` gives the "not shown" line).
- Mark: `LumeoMark` (dark and light cuts). Atmosphere: existing plum bloom token, `.dot-grid-bg` at lower opacity.

**Screenshots** (`shots/`): `c-1440x900-dark.png`, `c-1920x1080-dark.png`, `c-390x844-dark.png`, `c-1440x900-light.png`, `c-mid-1.png` (t about 1.1 s, opening rolling), `c-mid-2.png` (t about 4.6 s, closing rolling), `c-hover-credits.png` (hover state), `c-focus-debits.png` (keyboard focus), `c-nojs-check.png` (static equivalent). Frozen frame for review: `concept-c.html#t=4.6`.
