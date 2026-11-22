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
