import type { ReactNode } from "react";
import { SmoothScroll } from "@/components/motion/smooth-scroll";

// Runs synchronously during HTML parsing, before first paint. Adds lp-js to <html>, which arms
// the motion-only hidden state in motion.css. Without JS the class never appears and every
// [data-reveal] element stays in its final visible state.
const LP_JS_INIT = "document.documentElement.classList.add('lp-js')";

// Marketing shell: skip link, motion provider (Lenis + GSAP bootstrap), then children.
// The page owns <main id="content"> so the nav sits above it and the footer renders as a
// contentinfo landmark.
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: LP_JS_INIT }} />
      <a href="#content" className="skip-link">Skip to content</a>
      <SmoothScroll>{children}</SmoothScroll>
    </>
  );
}
