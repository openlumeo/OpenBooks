# Flagship hero research (2025-2026) for the Open Books concepts

Scope: public marketing pages and general technique knowledge. No project data used.
Tags: [V] = fetched this run with WebFetch (returns extracted text, not pixels, so visual claims are not verified). [K] = from memory, unverified this run.

## 1. What distinguishes premium heroes today

Common pattern across the sites: one sentence H1, one subhead, one or two CTAs, and a single product or brand object. Premium comes from what is left out.

| Site | Composition (observed) | Staging of product UI |
|---|---|---|
| Linear | H1 "The product development system for teams and agents." Subhead, then "Get started" and "Contact sales". A small "NewLoops" announcement sits above the H1. | [V] Hero object is an issue view (title "Faster app launch", ID and "1 / 84" counter). [K] Dark UI, shown flat, not heavily tilted. |
| Stripe | H1 "Financial infrastructure to grow your revenue." One CTA in hero ("Request an invite"). | [V] Background asset is named "wave-fallback-desktop", i.e. a decorative wave with a static fallback. [V] Customer logo strip is duplicated in markup (looping marquee). [V] Top banner announces an acquisition, which pushes the hero down. |
| Vercel | H1 "Agentic Infrastructure" (one line). Subhead plus three bullets. "Deploy now" and "Talk to sales". | [V] Hero is text-led with no product object in the extract. [V] Bullets list concrete surfaces (API, CLI, MCP, Skills). |
| Ramp | H1 "Time is money. Save both." Email field plus "Get started for free". | [V] A single stat line sits in the hero ("0.9999521%"). [V] Small "AGENTS AT WORK TODAY:" label above logos. [K] Logo wall below the fold. |
| Mercury | H1 "Radically different banking." Email field above "Open account", secondary "Launch demo". | [V] Background is an animated pair of frames ("hero_start_frame" / "hero_end_frame"), so motion is a looping background, not a UI tilt. [V] Regulatory line directly under the form. |
| Plaid | H1 "Turn data into revolutionary financial products." Two CTAs ("Talk with our team", "Start building"). | [V] Decorative rainbow gradient strip and a mascot illustration in mobile/desktop/wink variants. No product UI in hero. |
| Raycast | H1 "Your shortcut to everything." Primary "Download for Mac" with system requirements and two alternates. | [V] Keyboard-key graphic follows the hero. [V] Announcement link ("Introducing Raycast MCP") sits inside the hero area. |
| Apple iPhone | Two-slide gallery, one product per slide, each a one-line H1 with "Buy" and "Learn more". | [V] Two switchable slides (#hero-gallery-item-1/2), each a single large product image on a plain field. Restraint is the product photo plus two links. |
| Arc, Mercury-style fintech dashboards | Not fetched. | [K] Arc uses a large soft-lit wallpaper-like field with the product as a floating window. Not verified. |

Observed patterns (what separates premium from cluttered):
- Headline length: 3 to 8 words, one line at 1440. Every H1 above is one sentence.
- Whitespace: the hero is the H1, subhead, and CTA, with the object either below the fold or as one image. Nothing else competes.
- Staging: product UI appears as a single plane (Linear), a single image (Apple), or a background loop (Mercury). None stack several panels.
- Motion: looping backgrounds (Mercury, Stripe) and logo marquees are common but are the first things to cut for a restrained premium read.
- Restraint is achieved by one CTA plus one text link, one object, and one announcement at most.

Rough targets for the Open Books hero (derived, not measured on sites): empty space at least 35% of the 1440x900 viewport, H1 at 64-88px, subhead at 18-20px, object occupying 30-45% of the viewport area.

## 2. Techniques for premium depth without heaviness

All snippets are plain CSS or GSAP sketches (<=15 lines each). Avoid backdrop-filter; keep blur on static layers.

### 2a. Perspective tilt with a rim-light hairline
```css
.stage { perspective: 1800px; }
.plane {
  position: relative; background: var(--surface);
  transform: rotateX(7deg) rotateY(-9deg);
  transform-style: preserve-3d;
  box-shadow: 0 50px 90px -50px rgba(0,0,0,.7);   /* soft, not hard offset */
}
.plane::before {                                   /* hairline rim, top-lit */
  content: ""; position: absolute; inset: 0; padding: 1px; pointer-events: none;
  background: linear-gradient(180deg, rgba(238,240,243,.32), rgba(238,240,243,0) 35%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
}
```
Keep tilt at 4-9 degrees. More reads as a template.

### 2b. Soft bloom via blurred radial layers (no backdrop-filter)
```css
.bloom {
  position: absolute; left: 50%; top: 30%; width: 900px; height: 520px;
  translate: -50% -50%; pointer-events: none; z-index: -1;
  background: radial-gradient(closest-side, rgba(173,230,196,.22), rgba(173,230,196,0) 70%);
  filter: blur(60px); opacity: .6;
}
.bloom--far { filter: blur(140px); opacity: .3; width: 1400px; height: 800px; }
```
Use at most two layers. Animate only opacity, never blur, on large layers.

### 2c. Film grain without banding
```css
.grain::after {
  content: ""; position: fixed; inset: 0; pointer-events: none; opacity: .05;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 .9 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
  background-size: 160px 160px;
}
```
Opacity 0.04-0.06. Noise is what prevents gradient banding on the dark ground (#0B0F08). Do not add it over text at higher opacity.

### 2d. Mask-image fades
```css
.hero-bleed {
  -webkit-mask-image: linear-gradient(#000 72%, transparent 100%);
          mask-image: linear-gradient(#000 72%, transparent 100%);
}
```
Use for the intentional bleed of the hero object past the fold. Do not mask text.

### 2e. Mechanical digit roll (GSAP sketch)
```js
// markup: each digit is <span class="col"><i>0</i><i>1</i>...<i>9</i></span>, overflow hidden, line-height 1
function rollTo(col, digit, dur = 0.9) {
  const h = col.firstElementChild.offsetHeight;          // one digit cell
  return gsap.to(col, { y: -digit * h, duration: dur, ease: "power3.out" });
}
// roll right-to-left with 70ms stagger so the least significant digit settles last
const cols = [...document.querySelectorAll(".roll .col")].reverse();
cols.forEach((c, i) => rollTo(c, +c.dataset.digit, 0.9 + i * 0.02).delay(i * 0.07));
```
Use Geist Mono with tabular-nums. Only digit cells move, the decimal point and separators are static text. Render the final string as-is (amount strings are never reformatted).

### 2f. Type tracking and optical size for large Geist
- Geist Sans has a weight axis only (no opsz axis). Compensate with tracking and leading, not variation.
- Display (>=64px): letter-spacing -0.04em (from brief), line-height 1.0-1.05, font-weight 400, font-feature-settings "ss01" only if it is preferred by the design system.
- Subhead (18-20px): letter-spacing 0 to -0.01em, line-height 1.5, max-width 56ch.
- Geist Mono labels (11-12px): uppercase, letter-spacing 0.08em to 0.12em, font-variant-numeric tabular-nums.
- Test the H1 at 1440 and 390; at 390 drop to 40-48px so it still lands in 3 lines or fewer.

### 2g. One entrance, expensive timing
```js
const tl = gsap.timeline({ defaults: { ease: "expo.out" } });
tl.from(".h1 .line", { yPercent: 105, duration: 1.1, stagger: 0.08 }, 0.1)
  .from(".lede", { autoAlpha: 0, y: 12, duration: 0.8 }, "-=0.7")
  .from(".plane", { y: 60, rotateX: 12, autoAlpha: 0, duration: 1.4 }, 0.2)
  .to(".stamp", { autoAlpha: 1, duration: 0.5, ease: "back.out(1.4)" }, "-=0.4");
```
Guidance: total timeline 1.6-2.0s; stagger 60-100ms; durations 0.5-1.4s; use expo.out or power3.out, avoid bouncy easing except the one stamp; animate at most three elements; the final state must equal the CSS default.

## 3. Hero anti-patterns that read as cheap (finance and infra)

1. Repeated ledgers or panels showing the same data twice. Avoid: one object, at most 5 rows, one caption.
2. Gradient text or glossy blobs. Avoid: flat text in #EEF0F3; mint only as a low-alpha bloom.
3. Stock devices, 3D phones, or stock people. Avoid: real UI crop at true scale, or the product alone.
4. Five small gestures (ticks, rings, underlines, badges, stamps). Avoid: one stamp, no decorative rules.
5. Oversized display type with tight leading that collides with the subhead. Avoid: 2-line cap and an explicit gap of at least 0.8em.
6. Template-looking tilt with a drop shadow. Avoid: 4-9 degree tilt, soft shadow, hairline rim only.
7. Low-contrast grey body copy on dark. Avoid: muted text at 64% alpha only for secondary labels; body at 4.5:1 minimum.
8. Looping marquees, counters, and autoplay backgrounds above the fold. Avoid: one entrance, then still (Stripe and Mercury show the cost of loops).

## 4. Eight measurable acceptance criteria (1440x900 screenshot)

1. Empty-space ratio: at least 35% of the viewport area has no text, UI, or object pixels (exclude nav pill and the 74px nav band).
2. Focal objects: exactly 1 hero object (count distinct bounded product or image regions; the stamp and the nav are excluded).
3. Headline: 1 or 2 lines at 1440, max 56ch subhead in 2 lines or fewer, directly under the H1.
4. Type scale: largest text in view is at most 88px; subhead 18-20px; no other text above 24px.
5. Colors in view: at most 4 distinct hue families (ground, text, mint, lavender); lavender occupies only the single RELEASED stamp.
6. CTAs: exactly 2 actions in the first viewport (one filled primary "Open workspace", one text link "Read the docs").
7. Ledger rows: 0 to 5 visible; no duplicate stage trail.
8. Nav: the 74px glass pill sits 12px from the top and the H1 starts at least 24px below its bottom edge (no overlap with the pill).

## 5. Accessibility and performance guardrails for scroll-driven hero motion

- LCP: target the H1 text as the LCP element (text is cheapest and has no network dependency). Do not make the product plane the LCP element. Target LCP under 2.5s on mobile.
- CLS: target 0. Give the product plane an explicit aspect-ratio. Load Geist with preload plus font-display: optional (or swap with size-adjust fallback metrics). Do not refresh ScrollTrigger after fonts settle in a way that shifts layout.
- Animate only transform and opacity. Avoid animating blur, filter, or box-shadow on large layers.
- Reduced motion: wrap all tweens in gsap.matchMedia("(prefers-reduced-motion: no-preference)"). Under reduce, the final frame is already the CSS default and no tweens run.
- No JS: the static markup is the composed final frame. Set the animation-ready class from JS only (html.js), so with JS disabled nothing is hidden.
- Scroll: no pinning on mobile; use ScrollTrigger scrub only if there is a real scroll story. Kill triggers on unmount.
- Pause and resume: pause the timeline on visibilitychange and when the tab is hidden.
- Contrast: body text 4.5:1 minimum on #0B0F08; large display text 3:1 minimum. Focus rings visible on the CTA and toggle.
- Stamp text is real text (not an image), so it is read by screen readers and is not lost under reduced motion.
- Measure with Lighthouse mobile and the Performance panel; record LCP, CLS, and dropped frames for the entrance.

## 6. Five most important takeaways

1. One H1 of 1-2 lines, one object, one primary action. The sites that look most premium (Linear, Apple, Vercel) show less, not more.
2. Product UI is staged as a single plane or single image with a 4-9 degree tilt, a hairline rim, and a soft shadow. Stacked panels read as clutter.
3. Depth comes from two blurred radial layers and a noise overlay at about 5% opacity, not from gradients, glass effects, or shadows.
4. Animate once: one timeline of about 1.8s with expo.out and 60-100ms stagger, transforms and opacity only. Loops and marquees (Stripe, Mercury) are the first thing to cut.
5. The final composed frame is the default. Reduced motion and no JS should show the same hero, and the H1 remains the LCP and the CLS stays at 0.
