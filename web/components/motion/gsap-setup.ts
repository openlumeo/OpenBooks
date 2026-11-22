'use client';

import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { DrawSVGPlugin } from 'gsap/DrawSVGPlugin';
import { SplitText } from 'gsap/SplitText';
import { MotionPathPlugin } from 'gsap/MotionPathPlugin';
import { MorphSVGPlugin } from 'gsap/MorphSVGPlugin';
import { Flip } from 'gsap/Flip';
import { ScrambleTextPlugin } from 'gsap/ScrambleTextPlugin';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(ScrollTrigger, DrawSVGPlugin, SplitText, MotionPathPlugin, MorphSVGPlugin, Flip, ScrambleTextPlugin, useGSAP);
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

export { gsap, ScrollTrigger, DrawSVGPlugin, SplitText, MotionPathPlugin, MorphSVGPlugin, Flip, ScrambleTextPlugin, useGSAP };
