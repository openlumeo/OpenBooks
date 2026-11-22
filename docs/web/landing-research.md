# Landing page upgrade: research notes

Scope: Next.js 16.4 / React 19.2 / pnpm marketing page. Dark green-black instrument-panel brand. Goal: institutional motion, scroll-driven product story, device frame, live demo, graceful degradation.

Verification legend: **[V]** checked in this run (npm registry, official page fetch, or local tarball measurement). **[K]** from prior knowledge, not re-checked here; verify before shipping.

---

## 1. Versions, license, bundle size

### Versions (npm view, this run)

| Package | Latest | Date in registry | Note |
|---|---|---|---|
| gsap | 3.15.1 | published 2026-11-04 [V] | |
| @gsap/react | 2.1.2 | doc modified 2026-11-11 [V] | publish date not read |
| lenis | 1.3.27 | doc modified 2026-10-29 [V] | package name is `lenis`; `@studio-freight/lenis` is legacy |
| three | 0.187.0 | doc modified 2026-10-30 [V] | |
| @react-three/fiber | 9.8.2 | doc modified 2026-10-21 [V] | |
| @react-three/drei | 10.7.9 | doc modified 2026-09-25 [V] | |

Pin exact versions in `package.json` and bump deliberately. Use `pnpm view <pkg> version time --json` to read exact publish dates when needed.

### License

- GSAP is free for commercial use under the standard license. The license page says commercial usage is covered and names SplitText and MorphSVGPlugin as previously members-only plugins now free for commercial use. (source: https://gsap.com/standard-license/) [V]
- The license page does not name ScrollTrigger or DrawSVGPlugin explicitly. They are in the public npm tarball (`dist/ScrollTrigger.min.js`, `dist/DrawSVGPlugin.min.js`, `dist/SplitText.min.js`, `dist/MorphSVGPlugin.min.js`). [V]
- Restrictions that matter: do not use GSAP in a tool that competes with Webflow's visual animation builder; no reverse engineering; keep proprietary notices. Using AI tools to write GSAP code is not restricted. [V]

### Gzip sizes

Measured locally by gzipping the published `dist` files from the npm tarballs (gzip level default, UMD minified builds). These are upper bounds for a tree-shaken ESM import.

| File | Minified | Gzip |
|---|---|---|
| gsap.min.js (core) | 73.4 kB | 28.5 kB [V] |
| ScrollTrigger.min.js | 44.7 kB | 18.0 kB [V] |
| DrawSVGPlugin.min.js | 4.4 kB | 2.2 kB [V] |
| SplitText.min.js | 8.0 kB | 3.6 kB [V] |
| MorphSVGPlugin.min.js | 21.2 kB | 9.5 kB [V] |
| lenis.min.js | 18.8 kB | 5.4 kB [V] |

Bundlephobia reports 26.8 kB gzip for the whole gsap package root import. (source: https://bundlephobia.com/package/gsap@3.15.1) [V]

Core + ScrollTrigger budget: about 27 to 46 kB gzip depending on tree-shaking. Plus Lenis about 5 kB. Total smooth-scroll and scroll-animation cost is roughly 35 to 50 kB gzip. Keep it in a client-only chunk so the server-rendered HTML does not depend on it.

Lenis bundlephobia lookup returned 429 in this run. Use the local number above.

three.js: not measured here (the `build/` folder shipped only unminified `three.core.js` and `three.module.js`). Check bundlephobia before deciding. [K] Full three.js with R3F and drei is commonly 150 to 250 kB gzip. Treat this as an estimate.

---

## 2. Lenis + GSAP ScrollTrigger in Next.js App Router

### Official wiring (Lenis README, GSAP section) [V]

Source: https://github.com/darkroomengineering/lenis

```js
const lenis = new Lenis();
lenis.on('scroll', ScrollTrigger.update);
gsap.ticker.add((time) => { lenis.raf(time * 1000); });
gsap.ticker.lagSmoothing(0);
```

### React and StrictMode notes

- Lenis ships a React entry (`lenis/react`) with `ReactLenis` and `useLenis`. [K] Some community sources say to set `autoRaf: false` when GSAP drives the loop, so Lenis does not run a second RAF. Check the current README for the exact option name before using.
- `gsap.ticker.lagSmoothing(0)` is global. Restore the default `gsap.ticker.lagSmoothing(500, 33)` on unmount.
- StrictMode runs effects twice on mount. Create the Lenis instance inside `useEffect` and destroy it in the cleanup. Do not create it at module scope.
- `gsap.registerPlugin` must run once at module load in a client module. Registering twice is harmless.

### `SmoothScroll` provider (TypeScript)

```tsx
'use client';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const LenisCtx = createContext<Lenis | null>(null);
export const useLenis = () => useContext(LenisCtx);

export function SmoothScroll({ children }: { children: ReactNode }) {
  const [lenis, setLenis] = useState<Lenis | null>(null);

  useEffect(() => {
    // Reduced motion: no smoothing. Native scroll still drives ScrollTrigger.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const instance = new Lenis({ autoRaf: false, duration: 1.1 }); // verify option name
    const onScroll = () => ScrollTrigger.update();
    const tick = (time: number) => instance.raf(time * 1000);

    instance.on('scroll', onScroll);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    setLenis(instance);

    return () => {
      gsap.ticker.remove(tick);
      gsap.ticker.lagSmoothing(500, 33);
      instance.destroy();   // removes its own listeners
      setLenis(null);
    };
  }, []);

  return <LenisCtx.Provider value={lenis}>{children}</LenisCtx.Provider>;
}
```

Mount it in `app/layout.tsx` around `children`. The layout stays a server component. Only the provider is a client component.

### `useGSAP` section example

Official React guide: https://gsap.com/resources/React/ [V]. `useGSAP` reverts animations and ScrollTriggers created in the callback on unmount. Wrap later event handlers in `contextSafe`.

```tsx
'use client';
import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger, useGSAP);

export function ProofSection() {
  const root = useRef<HTMLElement>(null);

  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.fromTo('.step', { opacity: 0.25 }, {
        opacity: 1, stagger: 0.2, ease: 'none',
        scrollTrigger: { trigger: root.current, start: 'top 70%', end: 'bottom 40%', scrub: true },
      });
    });
    // Reduced-motion branch: nothing animates, final state is already in the markup.
  }, { scope: root });

  return <section ref={root}><div className="step">Matched</div></section>;
}
```

Note: `gsap.matchMedia()` is documented at https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/ [V]. Animations inside a handler revert automatically when the query stops matching. `gsap.matchMediaRefresh()` re-runs handlers when a reduced-motion toggle changes.

### Anchor links

Lenis intercepts native scroll, so `href="#id"` jumps will not animate by default. Route them through Lenis:

```ts
document.addEventListener('click', (e) => {
  const a = (e.target as Element).closest<HTMLAnchorElement>('a[href^="#"]');
  if (!a) return;
  const el = document.querySelector(a.getAttribute('href')!);
  if (el && lenis) { e.preventDefault(); lenis.scrollTo(el as HTMLElement, { offset: -64 }); }
});
```

Do not also set `scroll-behavior: smooth` in CSS. The two fight.

### Fixed and sticky elements

- `position: fixed` works with Lenis (Lenis moves the document, not the fixed layer).
- `position: sticky` works if no ancestor has `overflow: hidden` or `overflow: clip` on the scroll axis. Check the page wrapper.
- Pinned ScrollTrigger sections (`pin: true`) use transforms and work with Lenis. Call `ScrollTrigger.refresh()` after fonts and images load.
- Modals that lock scroll: call `lenis.stop()` on open and `lenis.start()` on close. Do not rely on `body { overflow: hidden }` alone.

### Reduced motion and degradation

- Server output contains the final visual state. Animations start from a "from" state only inside a client effect that runs when motion is allowed. If JS is off, the page shows the end state.
- `respectReducedMotion` in Lenis defaults to true. [V] (source: Lenis README).

---

## 3. Parallax with ScrollTrigger scrub

Pattern list:

- Animate only `transform` and `opacity`. Never `top`, `margin`, or `background-position` on scroll.
- Use `yPercent` (not `y` in px) so offsets scale with element size and avoid layout reads.
- `ease: 'none'` with `scrub: true` (or a small number like `scrub: 0.6`) so the scroll position maps 1:1 to progress.
- Set `will-change: transform` only on the few layers that move, and only while in view. Remove it otherwise. Do not put it on every element.
- Keep parallax depth small: 4 to 12 percent of element height, 2 to 3 layers max. Large offsets look cheap.
- Disable on `(pointer: coarse)` if profiling shows jank on low-end Android, and always on `prefers-reduced-motion: reduce`.
- Use `ScrollTrigger.batch` or one timeline for many elements instead of many triggers.
- Avoid `backdrop-filter` on animated layers; it is the common cause of mobile frame drops.
- Pause offscreen work with `scrollTrigger.toggleActions` or `ScrollTrigger` `onToggle`.

```ts
gsap.to('.layer-back', {
  yPercent: -10, ease: 'none',
  scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: 0.6 },
});
```

---

## 4. Sketch annotations (hand-drawn SVG, GSAP DrawSVGPlugin)

### Authoring the paths

Two options:

- **Hand-authored cubic paths** (recommended). Draw 2 to 4 quadratic or cubic curves per mark in a vector editor, then copy `d` into code. Deterministic, small, no runtime cost.
- **roughjs-style wobble, generated offline.** `roughjs` (MIT) can generate jittered paths. Run it once in a script, save the `d` strings as constants. Do not ship roughjs at runtime; it adds bundle weight for no gain.

Keep marks sparse: one arrow, one circle, one underline per section. Hand-drawn feel comes from slight overshoot at stroke ends, not from many strokes.

### Pattern

```tsx
// Decorative. Hidden from assistive tech.
<svg aria-hidden="true" focusable="false" viewBox="0 0 220 60" className="sketch-underline">
  <path d="M4 44 C60 12, 130 58, 214 18" fill="none"
        stroke="var(--mint)" strokeWidth="1.6" strokeLinecap="round" />
</svg>
```

```ts
import { DrawSVGPlugin } from 'gsap/DrawSVGPlugin';
gsap.registerPlugin(DrawSVGPlugin);

gsap.fromTo('.sketch-underline path',
  { drawSVG: '0% 0%' },
  { drawSVG: '0% 100%', duration: 0.9, ease: 'power2.out',
    scrollTrigger: { trigger: '.sketch-underline', start: 'top 80%', once: true } });
```

- Use `once: true` for annotations. Scrubbed drawing feels like a loading bar.
- Set `stroke` and `fill` through CSS variables from the brand tokens so light and dark themes both work.
- Without JS the path renders fully (it is the default SVG state), which is the correct final frame.
- Accessibility: `aria-hidden="true"` and `focusable="false"` on the SVG. Put the meaning in real text. Do not use sketches as the only indicator of a value.

---

## 5. 3D: CSS 3D + GSAP vs three.js / R3F

| | (a) CSS 3D + GSAP | (b) three.js / R3F |
|---|---|---|
| Bundle | 0 kB extra (GSAP already loaded) | three + R3F + drei, est. 150 to 250 kB gzip [K] |
| A11y | DOM elements, real text, easy to hide with `aria-hidden` | Canvas, needs a text alternative and a non-canvas fallback |
| Fallback | Works with JS off (static stack) | Needs a static image shown until canvas is ready |
| Mobile perf | Good with transform and opacity only | GPU cost; needs DPR caps and pausing offscreen |
| Next.js | No SSR issue | `next/dynamic(() => import(...), { ssr: false })`, client only [K] |
| Visual range | Stacked sheets, tilt, parallax, shadows | Real lighting, geometry, shaders |

**Recommendation: (a) CSS 3D driven by GSAP.** A tilting stack of translucent ledger sheets with `transform-style: preserve-3d`, `perspective` on the parent, pointer tilt through `gsap.quickTo` on `rotateX` and `rotateY`, and scroll-scrubbed layer separation. It reads as industrial and precise, costs no extra weight, has no canvas for screen readers, and degrades to a flat stack. Pointer tilt should be off for `(pointer: coarse)` and reduced motion.

Skip three.js unless the product itself needs 3D. If it is added later, load it in a route segment with `ssr: false` and a static poster image as the first paint.

---

## 6. Device frames and product screenshots

### Options

- **Own CSS/SVG frame (recommended).** Rounded rectangle, bezel, hairline edge, and a shadow, all in our tokens. Generic: no Apple logo, no Apple-specific notch or dynamic-island geometry, no Apple color names. Resolution-independent and themable.
- **Third-party CSS device libraries.** devices.css (Rattone/devices.css) and similar Marvel-derived packages draw Apple-style MacBook and iPhone frames. Its MIT license is listed on secondary sites only; the GitHub page returned 404 in this run. [V] for the 404; license claim unverified. Do not use these for an Apple-look marketing site.
- **Images.** A PNG/WebP device mockup is fixed-resolution and harder to theme. Use only if it is your own asset under a license you hold.

### Apple guidance (state plainly)

Source: https://www.apple.com/legal/intellectual-property/guidelinesfor3rdparties.html [V] (fetched; summary below).

- Using the Apple logo or any Apple-owned logo or icon on a website requires express written trademark permission.
- Showing an image of an Apple product in promotional material is described as generally allowed for developers whose product is compatible, but only if it is an actual photograph of the genuine product, shown in the best light, and not an artist's rendering.
- Photographs owned or licensed by Apple need express written permission.
- Apple does not support others using product names or product images in advertising in a way that suggests endorsement.
- The Apple affiliate guide says product photos are limited to approved affiliates and third parties with permission, and that you should not copy images from apple.com. (source: https://apple.com/shop/Catalog/US/Images/affiliates/affiliate-banners-guide.pdf) [V]

**What is plainly allowed:** a factual "compatible with macOS / iOS" word mark in referential text, as long as it is true and not implying endorsement.
**What is not allowed without permission:** Apple logos, Apple product photos, and Apple-branded device renders used to imply a relationship.
**Our call:** Do not use Apple device renders or copied Apple frames. Build a generic laptop and phone frame. It is a design choice, not legal advice; get counsel to sign off if the frame looks close to Apple hardware.

### Frame build

```tsx
import Image from 'next/image';

<figure className="device device--laptop" style={{ aspectRatio: '16 / 10' }}>
  <div className="device__screen">
    <Image
      src="/marketing/ledger-dark.webp"
      alt="Ledger view showing a verified line item with source reference"
      width={1600} height={1000}
      sizes="(min-width: 900px) 960px, 100vw"
      className="device__img"
    />
  </div>
</figure>
```

- `width` and `height` plus `aspect-ratio` reserve space and prevent CLS.
- `next/image` serves responsive WebP/AVIF. Use `sizes` so mobile does not download the desktop image.
- Light and dark: two `next/image` elements with `className` toggled by `[data-theme]`, or a `<picture>` with `media="(prefers-color-scheme: dark)"`. Render only one for each theme to save bytes. For the `<picture>` option the `<img>` fallback must carry width and height too.
- The screenshot is the real app UI, captured at 2x, with personal or client data replaced by sample data.

---

## 7. Live end-to-end demo UX

Patterns used by credible data and fintech sites [K]:

- Scripted replay of a recorded real run by default. Live mode is an explicit button.
- A "stage trail": a horizontal list of pipeline stages (ingest, extract, verify, decide). Stages light as events arrive.
- Drag-a-sample affordance: a drop zone with a sample file pre-loaded and a keyboard-equivalent "Use sample" button.
- Streamed verdict: the decision and the reason lines appear one at a time, with the source reference next to each.

### Fallback when the backend is unavailable

1. Ship a recorded run as static JSON in the bundle or `public/`. It contains the real event sequence captured from a real backend run, timestamps included.
2. The replay runs the recorded events on a timer, scaled by `prefers-reduced-motion` (instant final state if reduced).
3. "Run live" calls the API. On network error or timeout, show "Live run unavailable. Showing the recorded run from [date]." and switch to replay. Never show an error that looks like a verdict.
4. Label the mode in the UI: "Recorded" or "Live". Never present a recording as live.

### Accessibility

- Stage trail uses a list with `aria-current="step"` on the active stage.
- Event log lives in an `aria-live="polite"` region, announcing one summary per stage (not every event). Throttle to avoid screen-reader spam.
- Every control is a real `button` or `input`. Drop zone has a keyboard-activated "Choose file" button.
- Reduced motion: no timer-driven stage animation; the final state is shown after one click.
- Results have text, not color alone: "Verified", "Refused", "Needs source".

---

## 8. Reference review

Observations below come from prior knowledge. They were not re-checked in this run, so verify each site before quoting it. No assets or wording copied.

**Stripe** [K]
- Strong use of a single display weight with generous line-height; body copy stays small and dense.
- Product UI is shown as layered, tilted cards with real data, not as stock device photos.
- Trust language is factual and numeric (volumes, uptime), with links to docs.

**Linear** [K]
- Product screenshots are cropped to the working area, with hairline borders and muted dark UI.
- Motion is restrained: small fades and transforms tied to scroll, not large parallax.
- Dense feature grids with consistent spacing and a monospaced label style.

**Plaid** [K]
- Developer-first flow: code snippet next to the explanation, with a live-looking response.
- Sections use plain statements of what the product does, then proof (customers, uptime).

**Ramp / Brex** [K]
- Finance-specific language: exact numbers, named controls ("approval", "limit"), short sentences.
- Product walkthroughs are scroll-linked sections with one screen per step.

**Vercel** [K]
- Heavy use of monospace for technical labels and status; black and white with one accent.
- Demos are interactive and fast to start, with a clear "try it" affordance.

**Bloomberg Professional** [K]
- Density over decoration: tables, tickers, and dense type. Very low motion.
- Trust comes from the product screens themselves and from restrained, formal copy.

### Eight design principles for our page

1. **Sticky product frame, steps change the screen.** The device frame stays pinned while the left column narrates steps; each step swaps the screen content (not the frame).
2. **Density with hierarchy.** Use one display size, one body size, and one mono label size. Avoid more than three type sizes above the fold.
3. **Restrained motion.** Scroll-scrub only for product and parallax; everything else fades once. No looping ambient motion.
4. **Proof before claims.** Show a real verification result before the headline promise is explained.
5. **Hairlines and grid, not shadows.** Borders and grid lines carry structure; shadows only under the device frame.
6. **Numbers are specific.** Use exact counts, times, and sources in examples. Avoid superlatives.
7. **Every animation has a static equivalent.** The final frame is the default; motion is an enhancement.
8. **One accent.** Mint is used for state (verified, active), never decoration.

---

## 9. Copywriting for accountants and CAs

Six principles:

1. **Say what was checked.** Name the source document and the check. "Checked against the bank statement" beats "AI verified".
2. **Give the refusal condition.** State when the system will not produce an answer. This is the brand.
3. **Use the accountant's nouns.** Ledger, voucher, source document, tie-out, variance. No "magic", "insight", "unlock".
4. **Short, declarative sentences.** One claim per sentence. Avoid stacked adjectives.
5. **Quantify or cite.** A number, a date, or a source reference in every claim.
6. **Admit limits in plain words.** "Does not verify handwritten invoices." Trust grows from stated limits.

Before and after:

1. Before: "Our AI intelligently guesses your numbers with confidence." After: "Every figure is traced to its source document. If a figure cannot be traced, it is marked refused."
2. Before: "Revolutionize your month-end close!" After: "Month-end close with a source reference on every line."
3. Before: "Trusted by thousands of firms worldwide." After: "Used by 14 firms in their 2026 year-end close. Each verdict links to its source." (Replace 14 with a real, verifiable number before publishing; do not ship placeholders.)

Product voice anchor: "Proven or refused, never guessed."

---

## Recommended stack and risks

- Stack: Next.js 16.4, React 19.2, pnpm, GSAP 3.15.1 (core, ScrollTrigger, DrawSVGPlugin only), @gsap/react 2.1.2, Lenis 1.3.27. Skip SplitText and MorphSVG unless a specific effect needs them.
- Lazy-load the whole motion layer in a client boundary; keep the static final frame in server HTML.
- 3D: CSS 3D with GSAP quickTo for tilt. No three.js in v1.
- Device frame: own generic CSS/SVG frame, no Apple logos, device renders, or Apple-specific geometry. Get legal review if the frame looks close to Apple hardware.
- Screenshots via `next/image` with width, height, `sizes`, and `aspect-ratio` to avoid CLS.
- Demo: recorded real run as default; live mode as explicit opt-in; label the mode; throttled `aria-live`.
- Risk: GSAP license wording for ScrollTrigger and DrawSVG is not explicit on the license page; the npm package includes them. Confirm with GSAP or Webflow before a paid-product launch.
- Risk: Lenis option names (`autoRaf`) and `off` vs unsubscribe API should be checked against the 1.3.27 README before merging.
- Risk: Lighthouse and CLS. Measure after adding GSAP; target LCP image and fonts first.
- Risk: Mobile jank from backdrop-filter and large parallax. Profile on a mid-range Android.
- Risk: Reference-site observations are from memory, not re-checked. Verify before quoting.
- Risk: Copy claims (firm counts, uptime) must be real before publishing.
- Risk: Lenis plus fixed headers and sticky sections in nested containers. Test with `overflow` ancestors.
