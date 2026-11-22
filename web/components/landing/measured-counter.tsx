// Animated figure: counts from 0 to `to` once it scrolls into view (ease-out cubic, ~900ms).
// SSR and no-JS render the final value. Reduced motion keeps the final value and never animates.
'use client';

import { useEffect, useRef } from "react";

const COUNT_MS = 900;

export function MeasuredCounter({ to }: { to: number }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const run = () => {
      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min((now - start) / COUNT_MS, 1);
        el.textContent = String(Math.round(to * (1 - (1 - t) ** 3)));
        if (t < 1) frame = requestAnimationFrame(step);
      };
      el.textContent = "0";
      frame = requestAnimationFrame(step);
    };
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        io.disconnect();
        run();
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [to]);

  return <span ref={ref}>{to}</span>;
}
