# Open Books Landing Page: Plan

Status: implemented. The hero was later redesigned (centred hero with an interactive ledger) and the copy is superseded by `docs/web/landing-copy-v2.md`. Mode: **Persuade**. Visual world: **inherited** (Lumeo DESIGN.md is binding, see `docs/DESIGN.md`). No new identity, no DESIGN.md change.

Decisions confirmed by the user:
- Landing lives at `/`. The developer docs index moves to `/docs`.
- Primary CTA: **Open workspace** (`/app`). Secondary: **Read the docs** (`/docs`).
- Nav is **floating**, holds **Docs** and **Open workspace**, and **shrinks once the page scrolls**.

## 1. Brief

- **Who must act:** a chartered accountant or bookkeeper in India with a pile of client files, or the developer who builds for them.
- **What they must believe:** this tool will not hand me a number I cannot defend. A file is released only when its own arithmetic ties out; otherwise it is refused with a reason.
- **Proof we actually have** (PRODUCT.md "Evidence on Hand"): the engine's gate, the six refusal codes, per-field evidence, and measured synthetic results (69 end-to-end cases, 27 released, 0 false accepts, 0 schema violations, verified in `docs/evidence/e2e_synthetic_model_scans.json`).
- **Must not appear:** real-world accuracy figures, customer names, testimonials, firm logos, compliance certifications, pricing, accounts, "SOC 2", "bank-grade", any hype. Maturity is stated plainly.
- **Success:** a visitor reaches `/app` and loads a sample, or reaches `/docs`.
- **Would feel wrong:** a generic fintech hero (gradient blob, "AI-powered", stat-card row, three identical feature cards), or anything that softens a refusal.

## 2. Concept: "The proof is the hero"

The first viewport shows the product's one idea as an object: a statement that ties out and its tampered twin that does not, side by side as flat instrument panels (`.recon` language). Left: opening + credits - debits = closing, every row mint, stamped RELEASED (the single lavender moment). Right: the same file with one amount changed, rose left border, `REFUSED · BALANCE_MISMATCH`, engine message verbatim. The visitor reads the product before reading any copy.

Rest of the page is a short argument, each section earning the next, with varied rhythm (no repeated card grid):

| # | Section | Job | Form |
|---|---|---|---|
| 0 | Floating nav | wayfinding | glass pill, shrinks on scroll |
| 1 | Hero | the idea as an object | H1 + lede + CTAs + ProofPair |
| 2 | How a file is proven | the gate | 5-stage trail (Detect, Parse, Normalise, Balance, Validate) plus the four checks as ledger rows |
| 3 | A refusal is an answer | trust through honesty | six codes mapped to the stage where each stops, one verbatim refusal |
| 4 | Traceable to the source | every figure has a source | one evidence record laid out: page, bbox, row, raw_text, method |
| 5 | What it reads | scope, honestly | four input groups; PayPal, Wise, 1099-B tagged UNVERIFIED |
| 6 | Ask, code counts | the Q&A rule | question, collapsed tool line, cited answer; "the model explains, code counts" |
| 7 | Measured, on synthetic data | evidence without overclaim | one ledger-style table, not a stat-card row; limits stated |
| 8 | Final CTA + footer | act | Open workspace, Read the docs, maturity note, processing statement |

Hierarchy intent: hero and section 2 carry visual weight; 3 and 4 are quiet and dense; 5 is a plain list; 6 is the second visual moment; 7 is small and sober.

## 3. Copy (use verbatim; do not invent claims)

- Eyebrow: `OPEN BOOKS BY LUMEO`
- H1: `Proven JSON, or a typed refusal.`
- Lede: `Open Books releases a financial file only when its own arithmetic proves it: opening plus transactions equals closing, running balances tie, printed totals match. Anything else comes back as a refusal that says why.`
- CTAs: `Open workspace` (to `/app`), `Read the docs` (to `/docs`)
- Maturity line (hero and footer): `EARLY RELEASE · TESTED ON SYNTHETIC DATA`
- Sec 2 heading: `A file is released only when it proves itself.` Rows: `Opening + transactions = closing`; `Running balance ties on every row`; `Settlement: gross - fees - tax = net`; `Printed totals match`. Note: `At least one check must be independent evidence printed in the document.` Footnote: `Optional model checks can only add doubt (LOW_CONFIDENCE). They never cause a release.`
- Sec 3 heading: `A refusal is an answer.` Body: `No partial output, no best guess with a confidence score. The refusal names the stage, the code and the engine's reason.` Codes by stage: Detect = `UNSUPPORTED_INPUT`, `UNKNOWN_LAYOUT`; Parse = `PARSE_ERROR`, `LOW_CONFIDENCE`; Balance = `BALANCE_MISMATCH`; Validate = `OUTPUT_INVALID`. Where the fix is known (missing opening balance or currency) the workspace offers it inline.
- Sec 4 heading: `Every figure traces to its source.` Body: `Each field carries its page, box, row, raw text and method.` Show one record taken from a real engine run on a sample, labelled `SYNTHETIC SAMPLE`.
- Sec 5 heading: `What it reads.` Groups: Bank statements, Gateway settlements, Tax documents, Excel workpapers. Layout names come only from `server/openbooks_server/catalog.py` (`FORMATS`). Tag PayPal activity, Wise statement and Form 1099-B `UNVERIFIED` with the note `Built from public descriptions, tested on synthetic files only.` Add: `Limit 20 MB per file.`
- Sec 6 heading: `The model explains. Code counts.` Body: `Totals and counts come from code over the released data, with file and record ids cited. The model never does arithmetic.` Example must be computed from `web/public/examples/statement.csv` and labelled `EXAMPLE`.
- Sec 7 heading: `Measured, on synthetic data.` Rows: `69 end-to-end cases`, `27 released`, `0 false accepts`, `0 schema violations`. Caption: `Synthetic files only. No real statements have been scored. Source: docs/evidence.`
- Footer: `Files are processed in memory and not stored on the server. Thread history stays in your browser.` (PRODUCT.md Operating Context.) Open decisions (accounts, retention terms) are not claimed either way.
- No em dashes. No exclamation marks. No "seamless", "powerful", "AI-powered", "effortless".

## 4. Design contract

From `docs/DESIGN.md` section 7, non-negotiable:
1. Radius 0 everywhere; the glass surface radius (`--glass-radius`, 20px) is the sole exception and is used only for the nav.
2. Text on accent fills uses `--on-accent`.
3. One lavender (`--accent-2`) moment per viewport: the hero RELEASED stamp. Nothing else lavender above the fold; later sections may use at most one each, never two in one viewport.
4. Geist (display) weight <= 500, H1/H2 only. Inter for readable text. Geist Mono uppercase, tracked, `tabular-nums` for labels, rows, figures.
5. Do not lower `--text-muted` alpha. Plum is atmosphere only. `--unmatched` is the only error colour.
6. Glass blur budget: 2 per viewport. The nav spends 1; no other blur on the landing page.
7. Every animated element renders correctly with JS off and with `prefers-reduced-motion`. Rows default to the reconciled (mint) state; any unmatched start-state is applied only when animation runs.
8. Use the type classes (`.t-display .t-h1`, `.t-h2`, `.t-lede`, `.eyebrow`, `.btn`, ...) from `web/app/brand/type-scale.css` and `site-chrome.css`. Never size headings inline.
9. Container `--content-max` 1280px, gutter 24px, ledes max 62ch, prose max 68ch. Section rhythm `clamp(64px, 9vw, 116px)`.
10. Motion: `--ease` and `--dur` only; entrances `fadeInUp` 800ms, 100ms stagger.
11. Brand assets: `LumeoMark` and `BrandLockup` from `web/components/brand/`; never redraw the wordmark.

Known gap: DESIGN.md names classes (`.glass`, `.recon`, `.section`, `.system-module`) that do **not** exist in `web/app/brand/*.css` or `app.css`. Build equivalents in landing CSS from the tokens (check `theme-tokens.css` for `--glass-*`, `--hairline`, `--mint-soft`). Do not edit the three verbatim brand files.

### Craft-floor adjustments (apply to every workstream)

- **No eyebrow or kicker above any heading.** Drop `OPEN BOOKS BY LUMEO` above the H1 and any section label above H2s; `Section` takes only a heading and body. Mono uppercase is kept for data: panel headers, ledger rows, stage names, figures, tags.
- **Colored left borders:** only the `.recon` ledger row (2px mint matched, 2px rose unmatched), which DESIGN.md pins as the signature. No other colored side borders on cards, callouts or list items.
- No gradient text, no nested cards, no hard offset shadows, no emoji or unicode glyphs as icons (use `lucide-react` at one stroke width), no icon+heading+text identical card grids, no section numbers, no hero-metric stat row. Shadows carry an offset and soft blur.
- Theme the browser surfaces: `::selection`, caret colour, scrollbars inside scrollable panels, `text-underline-offset`, `font-variant-numeric: tabular-nums` on all figures.
- One authored motion moment (hero stage trail). Section reveals are subtle and not identical on every section.

### Floating nav spec

- `position: fixed`, inset `top: 12px`, horizontally centered, width `min(100% - 2 * var(--gutter), 1120px)`. Glass surface (`--glass-radius`, translucent fill, brighter top border, real `backdrop-filter` with `@supports` solid fallback). This is the page's one blur.
- Contents, left to right: `BrandLockup` (links to `/`), spacer, `Docs` (to `/docs`), `Open workspace` primary `.btn` (to `/app`), `ThemeToggle`. Labels in Inter 500 14px. On narrow widths (<= 560px) the lockup collapses to `LumeoMark` and `Docs` stays visible; nothing hides behind a hamburger because there are only two links.
- **Shrink on scroll:** a client component `LandingNav` sets `data-scrolled="true"` on the nav when a 1px sentinel at the top of the page leaves the viewport (IntersectionObserver, no scroll listener, no layout thrash). Expanded: width as above, block padding ~14px, mark 28px. Shrunk: width `min(100% - 2 * var(--gutter), 720px)`, block padding ~8px, mark 22px, `top: 8px`. Transition `width`, `padding`, `top` over `--dur`-based 300ms with `--ease`; contain it with `will-change: width` only during the transition. Reserve space so content never jumps (nav is out of flow, hero has top padding for the expanded height).
- Without JS: stays expanded and fully functional. Reduced motion: state still changes, transition duration 0.
- Keyboard: skip link `Skip to content` first in tab order, 3px focus outline offset on glass, links have real hit areas >= 44px tall at all states, including shrunk.
- Include `aria-label="Primary"` on the `<nav>`; `Open workspace` is a link, not a button.

### Motion and imagery

- Hero stage trail: CSS-only, the five stages light mint in sequence once on load (stagger 100ms steps); final state is the default rendered state.
- Section reveals: CSS only (`animation-timeline: view()` inside `@supports`, otherwise visible). Nothing starts hidden.
- No stock imagery, no illustrations of people, no generated art. The visuals are the real artefacts: ledger rows, stage trail, evidence record. Optional fine grain and one plum bloom bottom-right at low opacity as in DESIGN.md; static.

### Responsive

- 1440, 1024, 768, 375. At <= 900px the ProofPair stacks (released above refused). Ledger rows may scroll horizontally inside their own panel only, with a visible focus ring; the page never scrolls horizontally. Touch targets >= 44px.

## 5. Routing change (Wave 0)

`/` is currently `web/app/(developers)/page.tsx` (docs index, fumadocs layout). Required edits:

- Move that page to `web/app/(developers)/docs/page.tsx` (keep `generateMetadata = () => docMetadata([])`). The existing `docs/[...slug]` catch-all does not match `/docs`, so this file is required.
- `web/lib/docs.ts`: `url` function returns `"/docs"` for empty slugs.
- `web/app/(developers)/layout.tsx`: nav `url` to `/docs`.
- `web/components/docs/article.tsx:34`: `page.url === "/"` becomes `"/docs"`.
- `web/components/workspace.tsx:141` (Developer docs link) and `web/components/sidebar.tsx:106` (`ob-maturity` link) point to `/docs`.
- `web/lib/site.ts` `pageMetadata` and `web/app/sitemap.ts`, `web/app/llms*` : check for assumptions that docs index is `/`; add `/` (landing) and `/docs` entries.
- `web/components/auth/auth-form.tsx:71` back link to `/` now correctly lands on the landing page; leave.
- Create `web/app/(marketing)/layout.tsx` (no fumadocs provider; skip link, `<main id="content">`) and `web/app/(marketing)/page.tsx`.
- Acceptance: `/`, `/docs`, `/docs/quickstart`, `/app`, `/llms.txt` all 200; `pnpm typecheck` and `pnpm build` pass.

## 6. Build order

Workstreams ran in waves; each workstream owned a disjoint set of files so they could run in parallel.

1. **Routing.** Everything in section 5. Acceptance as listed there.
2. **Foundation.** `web/app/styles/landing.css` (one `@import` line added to `web/app/globals.css`), `landing-nav`, `site-footer`, the shared `Section` wrapper and the shared `.recon` panel and ledger-row primitives (`data-state="matched|unmatched"`). Acceptance: the nav toggles `data-scrolled` on scroll, works with JS disabled, keeps keyboard tab order.
3. **Sections (in parallel).** Hero and proof pair (`proof-data.ts` comes from a real engine run on a golden sample and its tampered twin; the refusal message is copied verbatim from the engine); how-proven and refusals (stage mapping imported from `web/lib/stages.ts`); trace and inputs (evidence record from a real run, formats from `catalog.FORMATS`); ask demo, measured and final CTA (figures read from `docs/evidence/e2e_synthetic_model_scans.json`, the Q&A example total computed from `statement.csv` with exact decimal arithmetic). Amounts are never `Number()`ed; strings are shown as emitted.
4. **Assembly.** `web/app/(marketing)/page.tsx`, metadata (title `Open Books by Lumeo`, canonical `/`, existing `opengraph-image`), JSON-LD via `structured-data.tsx` (SoftwareApplication, no ratings, price or offers), sitemap entry.
5. **Verification.** `pnpm test`, `pnpm typecheck`, `pnpm build`; the design linter once after build; screenshots at 1440, 1024, 768 and 375 in dark and light, with JS disabled and with `prefers-reduced-motion`; horizontal overflow, contrast, focus visibility, tab order and console errors; `/docs`, `/docs/quickstart`, `/app` and `/llms.txt` still return 200.
6. **Fixes.** Findings are triaged and fixed per file group, then the checks re-run. Done when the linter is clean or each finding is justified, there is no horizontal scroll at 375, all contrast pairs pass AA, and no claim appears outside section 3.

## 7. Risks

- Invented proof or reflowed copy. Mitigation: copy is frozen in section 3 and rendered text is diffed against it.
- Lavender or blur budget overrun. Mitigation: both are counted per viewport at each breakpoint.
- Routing change breaks inbound links. Mitigation: the routing acceptance covers the URL list; consider a `/docs` redirect note in the README.
- Numbers drifting from evidence files. Mitigation: constants cite their source file and are re-read from the JSON.
- Refusal message copied from memory. Mitigation: it is taken from a real engine run.

## 8. Open items for the user (not blocking the plan)

- Whether a short "Try a sample" affordance on the landing page should deep-link `/app` with a sample preselected (needs a query-param hook in the workspace; out of scope unless requested).
- Hosted terms: accounts and data-retention wording stay unclaimed until those decisions land (PRODUCT.md open decisions).

## Owner decision: square edges

Dated 2026-11-22.

- Radius 0 everywhere on the landing page, including the floating nav (`.lp-glass`). This overrides the DESIGN.md glass exception for this surface; the nav keeps its translucent fill, hairline border and single backdrop blur.
- Laptop device frames (`DeviceFrame`) keep their hardware bezel rounding; the screen contents stay square.
- The hero horizon hairline above the ALTER ONE BALANCE switch is removed.
- Round dots (live/pulse indicators) become squares.
