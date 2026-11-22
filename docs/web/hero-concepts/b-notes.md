# Concept B, "The Monolith"

**Idea.** A centred, cinematic launch composition: one large ledger instrument, seen in perspective, rises from a horizon and bleeds past the fold. It is a monument to a number that ties out. The visitor reads one headline and one lede, then sees a released statement that stands on its own.

**What the visitor sees.** Headline (2 lines, Geist 400, -0.04em) and a 2-line lede, with two CTAs. Below, the instrument: a slim mint rail along its top edge, the lavender RELEASED stamp landed on that rail, a statement header, opening 1000.00, five rows with mint tie bars, a gap marker, closing 5100.40 and the equation 1000.00 + 6857.26 - 2756.86 = 5100.40. Behind it: plum atmosphere, a restrained mint bloom, a 1px horizon at the instrument's base, and a back plane of faint ledger lines. Only the nav pill floats above.

**Motion timeline.**
- Load (CSS only, once): headline and lede fade up (1.1s). The instrument slides up 140px and settles (1.7s, delayed 0.2s). No looping motion.
- Scroll (GSAP ScrollTrigger, pinned hero, end +=120%, scrub: true, ease none):
  - 0.00-0.70: monument tilts from rotateX 18 to 0 and rises to the vertical centre.
  - 0.00-1.00: back plane parallax (about 0.4x the front travel).
  - 0.00-0.50: lead (headline, lede, CTAs) moves up out of the viewport.
  - 0.30-0.84: each row's tie bar retracts and redraws in turn (0.11 stagger). The end state is all tied.
  - 0.90-1.00: the stamp lands with one press (scale 1 to 0.94 to 1).
- Only transform is animated. The rest pose equals the flat CSS pose with JS off.

**Interaction and keyboard.** The scroll is the only interaction. The theme toggle is a real button (aria-label and aria-pressed). It stores `b-theme` in localStorage inside a try/catch. Tab order is nav, then CTAs. Focus rings use the 2px accent outline. Nothing is keyboard-trapped; the pin releases after 120% of a viewport.

**Degradation.**
- No JS: the static CSS is the finished composition (perspective pose, all rows tied, stamp landed, lead visible).
- prefers-reduced-motion: the CSS entrance is disabled and GSAP is not started. The page is the still, with no pin.
- Light theme: via `data-theme="light"` on `<html>`. The plum atmosphere is removed; the bloom turns mint-soft.

**Rules checked.** Radius 0 everywhere except the nav glass. Geist 400 only. Lavender appears only on the stamp. Figures are the frozen proof-data strings, unconverted. The lede is trimmed (no added claims). Five rows at most, with no row count labels and no stage trail.

**Build in the real site.**
- Replace the static nav with the existing glass pill component (`web/components/landing/*`).
- Put the instrument in a `web/components/landing/` component fed by `proof-data.ts` (`RELEASED.rows`, `opening`, `closing`, `creditTotal`, `debitTotal`).
- Use the `web/components/motion/*` primitives for the load entrance and reuse the existing GSAP and Lenis setup. Register ScrollTrigger once, and kill and rebuild the timeline on resize.
- Keep the CSS rest pose as the default and put every scrub value in JS, so no-JS and reduced motion are correct without extra code.
