/* docs: Single import point for GSAP in the marketing motion layer.
 *   import { gsap, ScrollTrigger, DrawSVGPlugin, SplitText, useGSAP } from '@/components/motion/gsap-setup';
 * Plugins register once at module load. Only touch the DOM inside effects or useGSAP.
 * Media queries for gsap.matchMedia(): MOTION_OK (any motion), FINE_POINTER_MOTION (motion + mouse),
 * DESKTOP_MOTION (>= 900px + motion, for pins and 3D), DESKTOP_FINE_MOTION (desktop + mouse). */
'use client';

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DrawSVGPlugin } from 'gsap/DrawSVGPlugin';
import { SplitText } from 'gsap/SplitText';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger, DrawSVGPlugin, SplitText, useGSAP);
// Mobile browsers resize the viewport on scroll; ignore that so pins do not jump.
ScrollTrigger.config({ ignoreMobileResize: true });

/** Motion allowed. Every animation branch is gated on this. */
export const MOTION_OK = '(prefers-reduced-motion: no-preference)';
/** Motion allowed and a fine (mouse) pointer. Used for parallax and tilt. */
export const FINE_POINTER_MOTION = '(prefers-reduced-motion: no-preference) and (pointer: fine)';
/** Motion allowed on desktop widths. Gate every pin and 3D scrub on this. */
export const DESKTOP_MOTION = '(min-width: 900px) and (prefers-reduced-motion: no-preference)';
/** Desktop motion with a fine (mouse) pointer. Used for pointer parallax and tilt. */
export const DESKTOP_FINE_MOTION =
  '(min-width: 900px) and (prefers-reduced-motion: no-preference) and (pointer: fine)';

// Set by any GSAP effect that has mounted. The provider's failsafe reads it.
let motionReady = false;
export function markMotionReady(): void {
  motionReady = true;
}
export function isMotionReady(): boolean {
  return motionReady;
}

export { gsap, ScrollTrigger, DrawSVGPlugin, SplitText, useGSAP };
