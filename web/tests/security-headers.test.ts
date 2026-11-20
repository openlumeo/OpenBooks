import { describe, expect, it } from "vitest";
import nextConfig, { CSP } from "../next.config";
import { rejectOversize } from "../lib/guards";
import { Markdown } from "../lib/markdown";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";

describe("security headers", () => {
  it("sends CSP, nosniff and frame denial on every path", async () => {
    const [rule] = await nextConfig.headers!();
    const h = Object.fromEntries(rule.headers.map((x) => [x.key, x.value]));
    expect(rule.source).toBe("/:path*");
    expect(h["Content-Security-Policy"]).toBe(CSP);
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["X-Frame-Options"]).toBe("DENY");
  });

  it("CSP blocks plugins, framing, base-tag and foreign form/connect targets", () => {
    for (const d of ["default-src 'self'", "object-src 'none'", "base-uri 'self'", "frame-ancestors 'none'", "form-action 'self'", "connect-src 'self'"]) {
      expect(CSP).toContain(d);
    }
    expect(CSP).not.toMatch(/\*|https?:/);
  });
});

describe("untrusted text rendering", () => {
  it("escapes markup in model output", () => {
    const html = renderToStaticMarkup(createElement(Markdown, { text: '<img src=x onerror=alert(1)> **<script>x</script>** `<b>`' }));
    expect(html).not.toMatch(/<img|<script|<b>/);
    expect(html).toContain("&lt;");
  });
});

describe("upload guard", () => {
  const req = (headers: Record<string, string>) => new Request("http://x/", { method: "POST", headers });
  it("requires a Content-Length, so chunked uploads cannot dodge the cap", () => {
    expect(rejectOversize(req({}), 10)?.status).toBe(411);
  });
  it("rejects bad and oversize lengths", () => {
    expect(rejectOversize(req({ "content-length": "-1" }), 10)?.status).toBe(411);
    expect(rejectOversize(req({ "content-length": "abc" }), 10)?.status).toBe(411);
    expect(rejectOversize(req({ "content-length": "11" }), 10)?.status).toBe(413);
    expect(rejectOversize(req({ "content-length": "10" }), 10)).toBeNull();
  });
});
