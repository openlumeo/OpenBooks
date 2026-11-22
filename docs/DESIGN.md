# Design System: Lumeo

**Scope:** the Lumeo brand and the marketing/product web surface in `frontend/web`.
**Source of truth in code:** [`frontend/web/app/(marketing)/globals.css`](<frontend/web/app/(marketing)/globals.css>) — every value below is a token declared there. This file explains the _why_; the CSS is the _what_. If the two disagree, the CSS wins and this file is stale.

> The mobile prototype's amber system in [`.agents/skills/design-system/SKILL.md`](.agents/skills/design-system/SKILL.md) is a **separate, older** language (amber on brown-black, DM Serif, rounded cards). Do not mix the two. Anything web-facing follows this document.

---

## 1. Visual Theme & Atmosphere

**Green-black instrument panel.** Dense, precise, engineered — a reconciliation terminal that happens to be beautiful, not a fintech landing page. The page reads near-black with a faint green cast at a glance; colour is rationed, never sprayed.

The mood is built from four moves:

- **Sharp geometry.** Radius is `0` almost everywhere — buttons, inputs, chips, icon tiles, images, timeline markers. Squared-off edges are the signature. The _only_ rounded elements are glass surfaces, at `--glass-radius` (20px). **This is a documented exception; do not generalise it.**
- **Hairlines over shadows.** Structure comes from 1px rules at 5–8% opacity, not from elevation. Depth is used sparingly and only on hover.
- **Atmosphere, not decoration.** A fixed plum bloom anchored bottom-right, a fine fractal grain at 16% opacity so large dark fields never band, and an optional vertical stripe field. All of it sits behind content at low opacity and never competes.
- **Mono as instrumentation.** Geist Mono in uppercase with wide tracking marks every label, timestamp, ledger row and figure — it is what makes the surface read as a machine rather than a brochure.

**Dark is the default theme**, not a mode. It lives on `:root`, so it is what paints when no preference is stored and when JS never runs. Light is a complete counterpart theme keyed to `[data-theme="light"]`, stamped on `<html>` before first paint.

---

## 2. Color Palette & Roles

### Surfaces

| Descriptive name                     | Dark      | Light     | Role                                                                                          |
| ------------------------------------ | --------- | --------- | --------------------------------------------------------------------------------------------- |
| **Deep Ledger Black-Green** (`--bg`) | `#0B0F08` | `#F7F9F6` | Page ground. On light it becomes a warm off-white with a faint green cast — never pure white. |
| **Slate Moss** (`--surface`)         | `#1E2820` | `#FFFFFF` | Cards, nav, elevated panels.                                                                  |
| **Lifted Moss** (`--surface-2`)      | `#2D3F31` | `#EEF2ED` | Hover states, secondary panels, input borders.                                                |

### Ink

| Descriptive name                | Dark            | Light     | Role                                                                                                                                       |
| ------------------------------- | --------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Cool Paper White** (`--text`) | `#EEF0F3`       | `#0B0F08` | Headings and primary copy. 18.3:1 on light bg.                                                                                             |
| **Muted Ink** (`--text-muted`)  | `#EEF0F3` @ 64% | `#52605A` | Body copy, secondary text. **Do not lower the dark alpha** — it is set exactly where it still clears 4.5:1 on both `--bg` and `--surface`. |
| **Faint Ink** (`--text-faint`)  | `#EEF0F3` @ 56% | `#5E6B65` | Meta, mono captions, table headers. Labels only, never running text.                                                                       |

### Accents — the load-bearing rule

`--accent` means **"the brand green," not "mint."** Mint is a _light_ colour: it carries text beautifully on green-black but collapses to ~1.4:1 on paper. So the semantic role flips per theme while the literal brand pales stay put.

| Descriptive name                | Dark                 | Light                | Role                                                                                                                                     |
| ------------------------------- | -------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Brand Green** (`--accent`)    | `#ADE6C4` (mint)     | `#0E6A47` (mint-ink) | Primary CTAs, links, active states, focus rings, live indicators.                                                                        |
| **Brand Violet** (`--accent-2`) | `#AD8FD5` (lavender) | `#6E4FA6` (lav-ink)  | Emphasis. **One moment per viewport, maximum.**                                                                                          |
| **On-Accent** (`--on-accent`)   | `#0B0F08`            | `#FFFFFF`            | Text sitting on an accent fill. Anything painting on accent **must** use this token — never a hardcoded near-black, never white-on-mint. |

| Brand pale                   | Value        | Role                                                 |
| ---------------------------- | ------------ | ---------------------------------------------------- |
| **Pale Mint** (`--mint`)     | `#ADE6C4`    | Fills, chips, washes, the logo. Never text on light. |
| **Pale Lavender** (`--lav`)  | `#AD8FD5`    | Fills only, same rule.                               |
| `--mint-soft` / `--lav-soft` | 12–14% tints | Chip backgrounds, hover washes.                      |

Verified pairs on light: text 18.3:1, muted 6.2:1, mint-ink 6.3:1, white-on-mint-ink 6.6:1, lav-ink 6.0:1 — all AA or better.

### Atmosphere & signal

| Descriptive name                     | Value                            | Role                                                                           |
| ------------------------------------ | -------------------------------- | ------------------------------------------------------------------------------ |
| **Bruised Plum** (`--plum`)          | `#231D29`                        | Background bloom only. **Never UI.**                                           |
| **Lifted Plum** (`--plum-2`)         | `#352C41`                        | Deeper atmosphere gradient stop.                                               |
| **Faint Alarm Rose** (`--unmatched`) | `#E6ADAD` dark / `#C0574F` light | The unmatched ledger row's left border. The only "error" colour in the system. |

There is no separate success green — reconciled _is_ `--accent`. That conflation is deliberate: in Lumeo, "green" and "matched" mean the same thing.

---

## 3. Typography Rules

Three families, each with a job it never leaves.

**Geist Sans** (`--font-sans`) — display only, H1 and H2.
Weight is **Regular (400), never above 500**. Tight optical tracking (`-0.04em` at H1, `-0.035em` at H2) and a `1.06` line height. Large type at light weight with negative tracking is the whole character — bolding it destroys the voice.

**Inter** (`--font-body`) — everything readable: body, ledes, H3, card titles, buttons, inputs. 400 for prose, 500 for titles and controls. Body sits at 16px/1.6; prose at 17px/1.7 capped to 68ch.

**Geist Mono** (`--font-mono`) — labels, eyebrows, ledger rows, amounts, timestamps, table headers, prices. Uppercase with `0.10–0.16em` tracking at 10–13px. All figures carry `font-variant-numeric: tabular-nums` so columns align.

### Scale

| Role       | Class                    | Family / weight | Size                                 |
| ---------- | ------------------------ | --------------- | ------------------------------------ |
| Display H1 | `.t-display .t-h1`       | Geist 400       | `clamp(40px, 6.4vw, 80px)`           |
| Display H2 | `.t-display .t-h2`       | Geist 400       | `clamp(30px, 4.2vw, 48px)`           |
| Section H3 | `.t-h3`                  | Inter 500       | `clamp(20px, 2.2vw, 24px)`           |
| Card title | `.t-card-title`          | Inter 500       | 17px                                 |
| Lede       | `.t-lede`                | Inter 400       | `clamp(16px, 1.5vw, 18px)`, max 62ch |
| Body       | `.t-body` / `.t-body-sm` | Inter 400       | 16px / 14px                          |
| Eyebrow    | `.eyebrow`               | Geist Mono      | 12px, `0.14em`, uppercase            |
| Ledger row | `.recon-row`             | Geist Mono      | 13px, tabular                        |

Use the classes. Never set a heading size inline — the scale is encoded once so a card title is the same 17px in every module.

---

## 4. Component Stylings

### Buttons — `.btn`

Sharp rectangles (`radius: 0`), Inter 500 at 14px, `13px 22px` padding, 9px gap to any icon.

- **Primary** (`.btn-primary-landing`, `.btn-hero-primary`): `--accent` fill, `--on-accent` text. Hover mixes 12% of `--accent-lift` into the fill (white on dark, black on light — hover always moves _away_ from the page), adds a 1px accent ring plus a soft accent-tinted drop, and lifts 1px. Active returns to rest.
- **Secondary** (`.btn-secondary-landing`): transparent on a `--surface-2` hairline. Hover brings the border to 45% accent and washes the fill.
- **Arrow affordance**: `.btn-arrow` icons translate `(2px, -2px)` on hover.
- **CTA dot** (`.cta-dot`): a lavender circle — one of the few round things in the system, and subject to the one-lavender-per-viewport rule.

### Cards & containers

Two distinct treatments — pick by context, don't blend.

- **Glass** (`.glass`, `.card`, `.system-module`, `.faq-item`): translucent fill + 1px border with a **brighter top edge** (`--glass-border-top`) that reads as light catching the lip, at the 20px `--glass-radius`. Padding is fluid, `clamp(20px, 8%, 52px)`.
  - `.glass` alone has **no blur** and is safe to repeat freely.
  - `.glass--blur` adds real `backdrop-filter`. **Budget: 2 per viewport** — the nav already composites one.
  - `.glass--dense` strengthens the fill for anything over three lines of running text, so the type still holds.
  - A `@supports` fallback paints a solid fill where `backdrop-filter` is unsupported, so glass never renders invisible.
- **Flat modules** (`.recon`, `.blog-card-media`): squared corners, `--hairline` border, semi-opaque `--surface`. This is the instrument-panel treatment.

`.system-module` hover is the system's signature interaction: border warms to 26% accent, the card lifts 2px, and a 1px mint gradient hairline (`.module-sweep`) sweeps left-to-right across the top edge over 500ms.

### Inputs & forms — `.field-input`

Squared corners, 1px `--surface-2` border, `color-mix`-ed translucent `--surface` fill, Inter 15px, `13px 15px` padding. Focus replaces the border with solid `--accent` and removes the default outline. Placeholders use `--text-faint`. Native `<select>` gets a hand-drawn CSS chevron so it keeps the sharp language instead of platform chrome.

Keyboard focus everywhere else is a `2px solid var(--accent)` outline at `2px` offset — on glass it goes to `3px` offset, because translucent surfaces swallow tight outlines.

### The Reconciliation Strip — `.recon`

The signature element. A flat, hairline-bordered panel with a mono uppercase header, a pulsing mint live-dot, and mono ledger rows carrying a 2px left border that turns mint when matched. The lavender `.recon-stamp` sits at a 2° rotation and is _the_ emphasis moment of the hero viewport.

Rows **default to the reconciled (mint) state**. GSAP sets the unmatched red start-state only when it actually runs, so a no-JS visitor lands on a correct final frame rather than a broken one.

---

## 5. Layout Principles

- **Container:** 1280px max (`--content-max`), 24px gutter (`--gutter`), centred. Re-declared unlayered in CSS specifically to beat Tailwind v4's own `.container` utility.
- **Vertical rhythm:** `.section` is `clamp(64px, 9vw, 116px)` block padding; `.section-tight` is `clamp(48px, 6vw, 80px)`. Whitespace is generous vertically and disciplined horizontally.
- **Measure caps:** ledes 62ch, prose 68ch. Long lines are the one thing the system never allows.
- **Orphan handling is explicit.** Grids that would strand a lone card span it instead: the 5-item engine grid runs 2-wide + 3-thirds, the 3-card pricing grid spans its third across a 2-column band. Never leave a widowed cell.
- **Texture:** `.dot-grid-bg` (24px radial dots) and `.fading-dot-grid` (radially masked, 26px) give sections quiet structure. `.stripe-field` lays ~20 percentage-sized bands so the count holds at any viewport instead of collapsing into fat columns on mobile — it is **static by design: no transition, no animation, no hover.**

### Motion

One easing curve, `cubic-bezier(0.16, 1, 0.3, 1)` (`--ease`), and one base duration, `150ms` (`--dur`). Entrances are `fadeInUp` over 800ms with 100ms stagger steps. Diagram animations are **paused by default** and only run while on screen, so off-screen SVGs never repaint.

`prefers-reduced-motion` collapses every duration to `0.001ms`, forces revealed elements visible, stops the rails marquee into a static wrapped row, and parks diagrams in their final state. Nothing is ever hidden behind an animation that might not run.

---

## 6. Logo & Brand Assets

The mark is a circular arrangement of vertical bars — a waveform closing into a loop, read as _reconciliation_. Official artwork ships as fixed-colour raster in [`frontend/web/public/brand/`](frontend/web/public/brand/):

| File                                    | Use                                           |
| --------------------------------------- | --------------------------------------------- |
| `mark-white.png` / `mark-black.png`     | Standalone mark, 185×196 intrinsic            |
| `lockup-white.png` / `lockup-black.png` | Horizontal mark + wordmark, 611×196 intrinsic |

Use the components, not the paths: [`LumeoMark`](frontend/web/components/lumeo-mark.tsx) (`size` prop) and [`LumeoLockup`](frontend/web/components/lumeo-lockup.tsx) (`markSize` prop, sized so the mark inside matches a standalone mark of the same value).

**Theme swap ships both cuts and hides one** via `.brand-asset--dark` / `.brand-asset--light`, deliberately unlayered so no utility can override it. The rule is written so the **dark asset is the default** — `<html>` carries no `data-theme` until a visitor explicitly picks light, so the correct cut paints on the first frame with no flash. Both images are `alt=""` / `aria-hidden`, because every usage sits inside a link already labelled "Lumeo home".

The wordmark is **part of the artwork**, not set in a webfont — it cannot drift if font loading fails. Do not reconstruct it in Geist.

**Blog poster covers** (`.cover`) are pinned to the light artwork in _both_ themes on purpose: a poster is a brand artefact, like a slide, and a deck does not restyle itself for dark mode.

---

## 7. Rules That Are Not Suggestions

1. **Radius stays 0.** Glass surfaces at 20px are the sole exception. Do not round buttons, inputs, chips, icons, or images.
2. **Never white text on mint, never near-black on mint-ink.** Always `--on-accent`.
3. **One lavender moment per viewport.** It is emphasis; two lavenders means zero.
4. **Geist never goes above 500 weight.**
5. **Don't lower `--text-muted` alpha.** It sits exactly at the contrast floor.
6. **Glass blur budget is 2 per viewport.** The nav spends one.
7. **Plum is atmosphere only** — never a UI surface, border, or text colour.
8. **No brand-colour third-party logos** on the rails strip. They render monochrome and only reveal true colour on hover, and on dark only for the three marks that clear 3:1 against `#0B0F08` (Upwork, Fiverr, Stripe).
9. **Every animated element must render correctly with JS off and motion reduced.** The reconciliation strip, the rails, and every diagram already do; anything new must too.
