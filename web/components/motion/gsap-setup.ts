/* docs: Single import point for GSAP in the marketing motion layer.
 *   import { gsap, ScrollTrigger, DrawSVGPlugin, useGSAP } from '@/components/motion/gsap-setup';
 * Plugins register once at module load. Only touch the DOM inside effects or useGSAP.
 * MOTION_OK / FINE_POINTER_MOTION are media queries for gsap.matchMedia(). */
'use client';

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DrawSVGPlugin } from 'gsap/DrawSVGPlugin';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger, DrawSVGPlugin, useGSAP);

/** Motion allowed. Every animation branch is gated on this. */
export const MOTION_OK = '(prefers-reduced-motion: no-preference)';
/** Motion allowed and a fine (mouse) pointer. Used for parallax and tilt. */
export const FINE_POINTER_MOTION = '(prefers-reduced-motion: no-preference) and (pointer: fine)';

// Set by any GSAP effect that has mounted. The provider's failsafe reads it.
let motionReady = false;
export function markMotionReady(): void {
  motionReady = true;
}
export function isMotionReady(): boolean {
  return motionReady;
}

export { gsap, ScrollTrigger, DrawSVGPlugin, useGSAP };
