# Hero redesign: shared brief for the concept mocks

Goal: a flagship, premium, institutional landing hero for Open Books by Lumeo. This is an exploration. Build standalone mock pages only. Do NOT edit anything under `web/`. The owner will approve one direction before it is built into the real site.

## Diagnosis of the current hero (why it feels cluttered)
1. Too many competing objects in one view: H1, a lede floating in a separate right column, two CTAs, a tagline, and two full ledger panels (18+ rows) that repeat nearly the same data.
2. The stage trail is drawn twice, ticks and labels everywhere, a ring, a stamp, an underline: five small gestures fighting for attention.
3. Density without a focal point: the eye has nowhere to land. Premium reads as restraint: one idea, one object, one action, generous space.
4. The lede is detached from the H1; the floating nav pill crowds the headline.

## Hero principles (binding for every concept)
- ONE hero object. One message. One primary action (a secondary text link is fine).
- Headline max 2 lines at 1440. Lede max 2 lines, directly under the headline, max 56ch. No separate column for the lede.
- At 1440x900, at least 35% of the first viewport is empty space (breathing room). Nothing is cut off awkwardly at the fold except an intentional bleed of the hero object.
- Show at most 5 ledger rows, or none. Never repeat the stage trail. No row count labels, no tag clutter.
- The RELEASED stamp (lavender) is the only lavender in the viewport, and it lands once.
- The nav is the existing floating glass pill (74px tall, 12px from top); content clears it.
- Premium cues to use deliberately: large Geist display at weight 400 with -0.04em tracking, a restrained mint glow (soft, low opacity bloom), layered planes with real depth, hairlines, fine grain, a single well-timed entrance (not many). Motion on load, plus at most one interaction.
- Static equivalent: the final composed frame must be the default (no JS / reduced motion).

## Brand (binding; docs/DESIGN.md)
Dark default: ground #0B0F08, surface #1E2820, lifted #2D3F31, text #EEF0F3, muted text 64% alpha, mint #ADE6C4 (brand green / state), lavender #AD8FD5 (emphasis, one moment), rose #E6ADAD (unmatched only), plum #231D29 (atmosphere only, never UI). Radius 0 for UI; glass nav 20px is the only exception. Geist Sans (display, weight 400, never above 500), Inter (body), Geist Mono uppercase tracked (labels, figures, tabular-nums). Light theme exists; provide a light screenshot too (tokens flip via `[data-theme="light"]` on `<html>`). No gradient text, no emoji, no stock imagery, no hard offset shadows, no eyebrow above headings, no section numbers.

## Content (frozen; do not invent claims)
- H1 options (pick one per concept, may tighten): `Every figure proven, or refused with a reason.`
- Lede: `Open Books checks each document's own arithmetic. If it ties out, you get structured data with the source of every figure. If it does not, you get the reason, never a guess.` (you may trim; do not add claims)
- CTA: primary `Open workspace` (to /app), secondary `Read the docs` (to /docs).
- Real figures only, from `web/components/landing/proof-data.ts`: released statement opening 1000.00, credits 6857.26, debits 2756.86, closing 5100.40 (INR), five rows (TXN 0 CR 1698.81 => 2698.81; TXN 1 DR 2071.01 => 627.80; TXN 2 DR 380.77 => 247.03; TXN 3 CR 494.51 => 741.54; TXN 4 DR 305.08 => 436.46). Tampered twin: TXN 4 balance printed 436.47 instead of 436.46; refusal `BALANCE_MISMATCH`, message `batch-1: running balance ties on every row (expected 8 rows, got 7 rows)`. Amount strings are never converted or reformatted.
- No SYNTHETIC / EARLY RELEASE wording.

## Technical setup for the mocks
- Standalone HTML in `d:\Code\openbooks\OpenBooks\docs\web\hero-concepts\` (one file per concept, plus its own `.css`/`.js` if you like, prefixed with your concept letter). Shared assets already exist in `vendor/`: `theme-tokens.css`, `type-scale.css`, `fonts/Geist-Variable.woff2`, `fonts/GeistMono-Variable.woff2`, `js/gsap.min.js`, `js/ScrollTrigger.min.js`, `js/CustomEase.min.js`. Reference them with relative paths (`vendor/...`) so the file also works via file://. Declare `@font-face` for the two Geist fonts yourself and define `--font-geist-sans` / `--font-geist-mono`; Inter may come from Google Fonts. Do not modify `vendor/`.
- Include the floating nav as static HTML/CSS (glass pill, lockup text `Open Books` + `BY LUMEO`, Docs, Open workspace, theme toggle) so the composition is judged in context.
- Include a few seconds of real scroll below the hero (a faint hint of the next section is enough) only if it helps the story.
- Screenshots: serve the folder with `python -m http.server <PORT> --directory d:\Code\openbooks\OpenBooks\docs\web\hero-concepts` (your own port, given in your task) and use the Playwright MCP tools. Save PNGs with absolute paths to `d:\Code\openbooks\OpenBooks\docs\web\hero-concepts\shots\<letter>-<name>.png`: 1440x900 dark (after the entrance has settled), 1920x1080 dark, 390x844 dark, 1440x900 light, plus 2 to 3 mid-animation frames if the concept has a timeline or interaction (with the interaction in its alternate state). LOOK at each screenshot (Read tool) and iterate until it is genuinely beautiful and uncluttered. Kill your server when finished.
- Also write `<letter>-notes.md` (max 40 lines): the idea in two sentences, what the visitor sees and does, motion timeline, interaction and keyboard behaviour, how it degrades (no JS / reduced motion), and how to build it in the real Next.js site with the existing pieces (`web/components/landing/*`, `web/components/motion/*`, GSAP + Lenis).
