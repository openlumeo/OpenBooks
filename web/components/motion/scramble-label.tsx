"use client";
import { useRef } from "react";
import { gsap, useGSAP, DESKTOP_MOTION, markMotionReady } from "@/components/motion/gsap-setup";

const WORD_LABEL = /^[A-Z][a-z]+(?: [a-z]+)*$/;

export function ScrambleLabel({ text }: { text: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(() => {
    markMotionReady();
    const el = ref.current;
    if (!el || !WORD_LABEL.test(text)) return;
    gsap.matchMedia().add(DESKTOP_MOTION, () => {
      gsap.set(el, { display: "inline-block", width: el.offsetWidth, whiteSpace: "nowrap", overflow: "hidden" });
      gsap.to(el, {
        scrambleText: { text, chars: "lowerCase", speed: 0.6 }, duration: 0.6,
        scrollTrigger: { trigger: el, start: "top 85%", once: true },
        onComplete: () => { gsap.set(el, { clearProps: "width,overflow,whiteSpace,display" }); },
      });
    });
  }, { scope: ref });
  return (
    <>
      <span className="sr-only">{text}</span>
      <span ref={ref} aria-hidden="true">{text}</span>
    </>
  );
}
