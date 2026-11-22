import type { ComponentProps } from "react";
import { Callout } from "fumadocs-ui/components/callout";

type CalloutProps = ComponentProps<typeof Callout>;

export function SketchCallout({ type, className, children, ...rest }: CalloutProps) {
  const kind = type ?? "info";
  return (
    <div className="ob-callout" data-type={kind}>
      <Callout {...rest} type={type} className={["ob-callout-body", className].filter(Boolean).join(" ")}>
        {children}
      </Callout>
      <svg className="ob-callout-corners" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <path d="M3 14 C 4 8, 6 5, 14 3" fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinecap="round" />
        <path d="M97 86 C 96 92, 94 95, 86 97" fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinecap="round" />
        <path d="M97 12 C 92 6, 88 4, 80 3" fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinecap="round" />
        <path d="M3 88 C 8 94, 12 96, 20 97" fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinecap="round" />
      </svg>
    </div>
  );
}
