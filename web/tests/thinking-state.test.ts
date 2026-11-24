import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ThinkingState, { THINKING_VERBS, formatElapsed } from "@/components/loading/thinking-state";

function render(props: Record<string, unknown> = {}): string {
  return renderToStaticMarkup(createElement(ThinkingState, props));
}

describe("ThinkingState", () => {
  it("renders an accessible status with the first verb and a timer", () => {
    const html = render();
    expect(html).toContain('role="status"');
    expect(html).toContain(`${THINKING_VERBS[0]}…`);
    expect(html).toContain("0.0s");
  });

  it("renders a square pixel grid with no illustration", () => {
    expect(render()).not.toContain("<svg");
    expect(render({ variant: "Orbit" })).not.toContain("<svg");
  });

  it("uses a fixed label instead of rotating verbs", () => {
    const html = render({ label: "Verifying statement.csv" });
    expect(html).toContain("Verifying statement.csv…");
    expect(html).not.toContain(`${THINKING_VERBS[0]}…`);
  });

  it("hides the timer on request", () => {
    expect(render({ showElapsed: false })).not.toContain("0.0s");
  });

  it("formats elapsed time in seconds and minutes", () => {
    expect(formatElapsed(0)).toBe("0.0s");
    expect(formatElapsed(599)).toBe("59.9s");
    expect(formatElapsed(600)).toBe("1m 0.0s");
    expect(formatElapsed(1234)).toBe("2m 3.4s");
  });
});
