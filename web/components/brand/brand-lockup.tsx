// "Open Books by Lumeo". The Lumeo mark is the official artwork; "Open Books" is the product name set in
// Geist at 400. The Lumeo WORDMARK is never redrawn in a webfont (DESIGN.md section 6), so the
// endorsement is written as plain mono text, not as a recreation of the Lumeo logotype.
import { LumeoMark } from "./lumeo-mark";

export function BrandLockup({ markSize = 26 }: { markSize?: number }) {
  return (
    <span className="ob-lockup">
      <LumeoMark size={markSize} priority />
      <span className="ob-lockup-text">
        <span className="ob-lockup-name">Open Books</span>
        <span className="ob-lockup-by">by Lumeo</span>
      </span>
    </span>
  );
}
