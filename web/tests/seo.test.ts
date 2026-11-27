import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/docs", () => ({
  docs: {
    getPages: () => [],
    getPage: () => ({
      url: "/docs/cli",
      data: { title: "CLI commands and exit codes", description: "CLI", toc: [], body: () => null },
    }),
  },
}));
vi.mock("@/lib/docs-markdown", () => ({
  docsText: (text: string) => new Response(text, { headers: { "content-type": "text/plain; charset=utf-8" } }),
  markdownPath: () => "/",
}));
vi.mock("next/font/google", () => ({ Inter: () => ({ variable: "" }) }));
vi.mock("geist/font/sans", () => ({ GeistSans: { variable: "" } }));
vi.mock("geist/font/mono", () => ({ GeistMono: { variable: "" } }));
vi.mock("@/components/brand/theme-script", () => ({ ThemeScript: () => null }));

import manifest from "@/app/manifest";
import robots from "@/app/robots";
import { metadata as rootMetadata } from "@/app/layout";
import { GET as llmsGET } from "@/app/llms.txt/route";
import { DocArticle } from "@/components/docs/article";
import { pageMetadata } from "@/lib/site";

const PACKAGE_NAMES = ["cli"] as const;
const PACKAGES_DIR = new URL("../../packages/js/", import.meta.url);
const AI_CRAWLERS = ["GPTBot", "ClaudeBot", "Claude-SearchBot", "PerplexityBot", "Perplexity-User", "Applebot-Extended"];
const PRIVATE_PATHS = ["/api/", "/auth/"];
const META_DESCRIPTION_MIN = 120;
const META_DESCRIPTION_MAX = 160;

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

describe("root metadata", () => {
  it("keeps the description between 120 and 160 characters", () => {
    const description = rootMetadata.description ?? "";
    expect(description.length).toBeGreaterThanOrEqual(META_DESCRIPTION_MIN);
    expect(description.length).toBeLessThanOrEqual(META_DESCRIPTION_MAX);
  });
});

describe("docs breadcrumb", () => {
  it("points the Developer docs crumb at /docs and the page crumb at its own URL", () => {
    const tree = JSON.stringify(DocArticle({ slug: ["cli"] }));
    expect(tree).toContain('{"@type":"ListItem","position":1,"name":"Developer docs","item":"https://books.openlumeo.com/docs"}');
    expect(tree).toContain('{"@type":"ListItem","position":2,"name":"CLI commands and exit codes","item":"https://books.openlumeo.com/docs/cli"}');
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
    expect(pkg.homepage).toBe("https://books.openlumeo.com");
    expect(pkg.bugs?.url).toBeTruthy();
  });
});
