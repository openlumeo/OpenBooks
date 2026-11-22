/* docs: const reduced = useReducedMotion();  // true when prefers-reduced-motion: reduce
 * Server snapshot is false (motion allowed); CSS already covers the static first paint.
 * Use for JS-driven decisions only. Pure CSS motion should use the media query instead. */
'use client';

import { useSyncExternalStore } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function subscribe(onChange: () => void): () => void {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener('change', onChange);
  return () => mq.removeEventListener('change', onChange);
}

function getSnapshot(): boolean {
  return window.matchMedia(QUERY).matches;
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
