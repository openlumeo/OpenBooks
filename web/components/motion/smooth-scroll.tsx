'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import Lenis from 'lenis';
import { gsap, ScrollTrigger, isMotionReady } from './gsap-setup';
import './motion.css';

const REDUCED = '(prefers-reduced-motion: reduce)';
const COARSE = '(pointer: coarse)';
const FAILSAFE_MS = 4000;

const LenisContext = createContext<Lenis | null>(null);

export function useLenis(): Lenis | null {
  return useContext(LenisContext);
}

export function SmoothScroll({ children }: { children: ReactNode }) {
  const [lenis, setLenis] = useState<Lenis | null>(null);

  useEffect(() => {
    let alive = true;
    const html = document.documentElement;
    html.classList.add('lp-js');

    const failsafe = window.setTimeout(() => {
      if (!isMotionReady()) html.classList.add('lp-motion-failsafe');
    }, FAILSAFE_MS);

    let teardown: (() => void) | undefined;
    if (!window.matchMedia(REDUCED).matches && !window.matchMedia(COARSE).matches) {
      const instance = new Lenis({ autoRaf: false, duration: 1.1 });
      const offScroll = instance.on('scroll', () => ScrollTrigger.update());
      const tick = (time: number) => instance.raf(time * 1000);
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);

      const onClick = (event: MouseEvent) => {
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        if (!(event.target instanceof Element)) return;
        const anchor = event.target.closest<HTMLAnchorElement>('a[href^="#"]');
        if (!anchor || (anchor.target && anchor.target !== '_self')) return;
        const hash = anchor.getAttribute('href') ?? '';
        if (hash.length < 2) return;
        const node = document.getElementById(decodeURIComponent(hash.slice(1)));
        if (!node) return;
        event.preventDefault();
        instance.scrollTo(node);
        window.history.pushState(null, '', hash);
      };
      document.addEventListener('click', onClick);

      setLenis(instance);
      teardown = () => {
        document.removeEventListener('click', onClick);
        gsap.ticker.remove(tick);
        gsap.ticker.lagSmoothing(500, 33);
        offScroll();
        instance.destroy();
        setLenis(null);
      };
    }

    void document.fonts?.ready.then(() => {
      if (alive) ScrollTrigger.refresh();
    });
    const onLoad = () => {
      if (alive) ScrollTrigger.refresh();
    };
    if (document.readyState !== 'complete') window.addEventListener('load', onLoad, { once: true });

    return () => {
      alive = false;
      window.removeEventListener('load', onLoad);
      window.clearTimeout(failsafe);
      teardown?.();
    };
  }, []);

  return <LenisContext.Provider value={lenis}>{children}</LenisContext.Provider>;
}
