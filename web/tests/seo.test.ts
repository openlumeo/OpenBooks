import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/docs", () => ({ docs: { getPages: () => [] } }));
vi.mock("@/lib/docs-markdown", () => ({
  docsText: (text: string) => new Response(text, { headers: { "content-type": "text/plain; charset=utf-8" } }),
  markdownPath: () => "/",
}));

import manifest from "@/app/manifest";
import robots from "@/app/robots";
import { GET as llmsGET } from "@/app/llms.txt/route";
import { pageMetadata } from "@/lib/site";

const PACKAGE_NAMES = ["cli", "core", "statements", "gateways", "doctor"] as const;
const PACKAGES_DIR = new URL("../../packages/js/", import.meta.url);
const AI_CRAWLERS = ["GPTBot", "ClaudeBot", "PerplexityBot"];
const PRIVATE_PATHS = ["/api/", "/auth/"];

describe("robots", () => {
  const config = robots();
  const rules = Array.isArray(config.rules) ? config.rules : [config.rules];

  it("has a wildcard rule and disallows private paths for each AI crawler", () => {
    expect(rules.find((rule) => rule.userAgent === "*")).toBeDefined();
    for (const userAgent of AI_CRAWLERS) {
      const rule = rules.find((candidate) => candidate.userAgent === userAgent);
      expect(rule, userAgent).toBeDefined();
      expect(rule?.disallow).toEqual(expect.arrayContaining(PRIVATE_PATHS));
    }
  });

  it("points the sitemap at /sitemap.xml", () => {
    const sitemaps = Array.isArray(config.sitemap) ? config.sitemap : [config.sitemap];
    expect(sitemaps[0]).toMatch(/\/sitemap\.xml$/);
  });
});

describe("manifest", () => {
  const app = manifest();

  it("names the app and starts at the root", () => {
    expect(app.name).toBe("Open Books by Lumeo");
    expect(app.start_url).toBe("/");
  });

  it("declares at least one icon", () => {
    expect(app.icons?.length ?? 0).toBeGreaterThanOrEqual(1);
  });
});

describe("pageMetadata", () => {
  const metadata = pageMetadata({ title: "Pricing", description: "Plans for teams", path: "/pricing" });

  it("uses the 1920x1080 og image", () => {
    const image = (metadata.openGraph?.images as Array<{ url: string; width: number; height: number }>)[0] as { url: string; width: number; height: number };
    expect(image.url).toBe("/og.png");
    expect(image.width).toBe(1920);
    expect(image.height).toBe(1080);
  });

  it("uses a large summary twitter card", () => {
    expect((metadata.twitter as { card: string }).card).toBe("summary_large_image");
  });
});

describe("llms.txt route", () => {
  it("lists the npm package, the MCP server and the 2 GB limit", async () => {
    const response = await llmsGET();
    const text = await response.text();
    expect(text).toContain("@lumeo_hq/openbooks");
    expect(text).toContain("openbooks-mcp");
    expect(text).toContain("2 GB");
  });
});

describe("published JS package metadata", () => {
  it.each(PACKAGE_NAMES)("%s has keywords, homepage and bugs url", (name) => {
    const pkg = JSON.parse(readFileSync(new URL(`${name}/package.json`, PACKAGES_DIR), "utf8")) as {
      keywords?: string[];
      homepage?: string;
      bugs?: { url?: string };
    };
    expect(pkg.keywords?.length ?? 0).toBeGreaterThan(0);
    expect(pkg.homepage).toBe("https://openbooks.lumeo.co.in");
    expect(pkg.bugs?.url).toBeTruthy();
  });
});
