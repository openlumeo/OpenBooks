import type { ReactNode } from "react";
import { SmoothScroll } from "@/components/motion/smooth-scroll";

const LP_JS_INIT = "document.documentElement.classList.add('lp-js')";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: LP_JS_INIT }} />
      <a href="#content" className="skip-link">Skip to content</a>
      <SmoothScroll>{children}</SmoothScroll>
    </>
  );
}
