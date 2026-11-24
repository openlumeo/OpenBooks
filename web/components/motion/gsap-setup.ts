'use client';

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';
import { Flip } from 'gsap/Flip';
import { ScrambleTextPlugin } from 'gsap/ScrambleTextPlugin';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger, SplitText, Flip, ScrambleTextPlugin, useGSAP);
ScrollTrigger.config({ ignoreMobileResize: true });

export const MOTION_OK = '(prefers-reduced-motion: no-preference)';
export const FINE_POINTER_MOTION = '(prefers-reduced-motion: no-preference) and (pointer: fine)';
export const DESKTOP_MOTION = '(min-width: 900px) and (prefers-reduced-motion: no-preference)';
export const DESKTOP_FINE_MOTION =
  '(min-width: 900px) and (prefers-reduced-motion: no-preference) and (pointer: fine)';
export const MOBILE_MOTION = '(max-width: 899px) and (prefers-reduced-motion: no-preference)';

let motionReady = false;
export function markMotionReady(): void {
  motionReady = true;
}
export function isMotionReady(): boolean {
  return motionReady;
}

export { gsap, ScrollTrigger, SplitText, Flip, ScrambleTextPlugin, useGSAP };
