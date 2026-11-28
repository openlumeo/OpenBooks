import { describe, expect, it } from "vitest";
import nextConfig, { CSP } from "../next.config";
import { rejectOversize } from "../lib/guards";
import { Markdown } from "../lib/markdown";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { vi } from "vitest";

vi.mock("server-only", () => ({}));

describe("engine proxy boundary", () => {
  it("blocks upstream redirects and refuses active response media", async () => {
    const { engineFetch, relay } = await import("../lib/server/engine");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ status: "ok" }));
    try {
      await engineFetch("/v1/health");
      expect(fetchMock.mock.calls[0]?.[1]?.redirect).toBe("error");
    } finally {
      fetchMock.mockRestore();
    }
    const rejected = relay(new Response("<html>unexpected gateway page</html>", {
      headers: { "content-type": "text/html", "cache-control": "public" },
    }));
    expect(rejected.status).toBe(502);
    expect(rejected.headers.get("content-type")).toContain("application/json");
    const normal = relay(new Response("data: ok", {
      headers: { "content-type": "text/event-stream", "cache-control": "public" },
    }), { "cache-control": "no-store" });
    expect(normal.headers.get("cache-control")).toBe("no-store");
    expect(await normal.text()).toBe("data: ok");
  });
});

describe("security headers", () => {
  it("sends CSP, nosniff and frame denial on every path", async () => {
    const rule = (await nextConfig.headers!())[0]!;
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
    expect(CSP.match(/https?:\/\/[^;\s]+/g)).toEqual(["https://uploads.books.openlumeo.com"]);
    expect(CSP).not.toContain("*");
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
