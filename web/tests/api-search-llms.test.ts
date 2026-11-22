import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const docsFake = vi.hoisted(() => {
  const page = (slugs: string[], title: string, description: string, body: string) => ({
    url: slugs.length === 0 ? "/docs" : "/docs/" + slugs.join("/"),
    slugs,
    data: {
      title,
      description,
      structuredData: {
        headings: [{ id: "h", content: title }],
        contents: [{ heading: "h", content: body }],
      },
      getText: async () => body,
    },
  });
  const pages = [
    page([], "Open Books docs", "Start here", "Welcome to the Open Books developer docs."),
    page(["getting-started"], "Getting started", "Install and run", "Install the package and run the first ledger check."),
    page(["cli", "run"], "Run command", "The run command", "Run a statement through the engine."),
  ];
  return {
    pages,
    getPages: () => pages,
    getPage: (slugs: string[]) => pages.find((p) => p.slugs.join("/") === slugs.join("/")),
    getPageTree: () => ({ type: "folder", children: pages.map((p) => ({ type: "page", name: p.data.title, url: p.url })) }),
  };
});
vi.mock("@/lib/docs", () => ({
  docs: { getPages: docsFake.getPages, getPage: docsFake.getPage, getPageTree: docsFake.getPageTree },
}));

import * as searchRoute from "@/app/api/search/route";
import * as llmsIndexRoute from "@/app/llms.txt/route";
const llmsIndex = llmsIndexRoute.GET;
import { GET as llmsFull } from "@/app/llms-full.txt/route";
import * as llmsMarkdown from "@/app/llms/[...slug]/route";

const mdGet = (slug: string[]) =>
  llmsMarkdown.GET(new Request("http://localhost/llms/" + slug.join("/")), { params: Promise.resolve({ slug }) });

describe("GET /api/search", () => {
  it("returns matching docs pages for a query", async () => {
    const res = await searchRoute.GET(new Request("http://localhost/api/search?query=ledger"));
    expect(res.status).toBe(200);
    const results = (await res.json()) as Array<{ url: string }>;
    expect(results.some((r) => r.url.startsWith("/docs/getting-started"))).toBe(true);
  });

  it("answers 200 with an empty result set for a query that matches nothing", async () => {
    const res = await searchRoute.GET(new Request("http://localhost/api/search?query=zzzqqqxxx"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual([]);
  });

  it("handles unicode queries without failing", async () => {
    for (const query of ["café", "日本語の検索", "🙂", "%E2%80%AE"]) {
      const res = await searchRoute.GET(new Request("http://localhost/api/search?query=" + encodeURIComponent(query)));
      expect(res.status, query).toBeLessThan(500);
    }
  });

  it("handles a very long query without failing", async () => {
    const res = await searchRoute.GET(new Request("http://localhost/api/search?query=" + "ledger ".repeat(5000)));
    expect(res.status).toBeLessThan(500);
  });

  it("answers an empty query without failing", async () => {
    const res = await searchRoute.GET(new Request("http://localhost/api/search?query="));
    expect(res.status).toBeLessThan(500);
  });

  it("exports only GET, so other methods are answered 405 by Next", () => {
    expect(Object.keys(searchRoute).filter((k) => /^[A-Z]+$/.test(k))).toEqual(["GET"]);
  });
});

describe("GET /llms.txt", () => {
  it("lists every docs page with its markdown link and description", async () => {
    const res = llmsIndex();
    const text = await res.text();
    expect(res.headers.get("content-type")).toBe("text/plain; charset=utf-8");
    expect(text).toContain("# Open Books by Lumeo");
    expect(text).toContain("[Getting started](https://openbooks.lumeo.co.in/llms/getting-started.md): Install and run");
    expect(text).toContain("https://openbooks.lumeo.co.in/llms-full.txt");
  });

  it("is marked noindex for search engines", () => {
    expect(llmsIndex().headers.get("x-robots-tag")).toBe("googlebot: noindex");
  });

  it("exports only GET", () => {
    expect(Object.keys(llmsIndexRoute).filter((k) => /^[A-Z]+$/.test(k))).toEqual(["GET"]);
  });
});

describe("GET /llms-full.txt", () => {
  it("concatenates every docs page separated by rule lines", async () => {
    const res = await llmsFull();
    const text = await res.text();
    expect(res.headers.get("content-type")).toBe("text/plain; charset=utf-8");
    expect(text).toContain("# Getting started");
    expect(text).toContain("Install the package and run the first ledger check.");
    expect(text.split("\n---\n\n").length).toBe(3);
  });
});

describe("GET /llms/[...slug]", () => {
  it("serves a docs page as markdown with a canonical link", async () => {
    const res = await mdGet(["getting-started.md"]);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("text/markdown; charset=utf-8");
    expect(res.headers.get("link")).toBe('<https://openbooks.lumeo.co.in/docs/getting-started>; rel="canonical"');
    expect(await res.text()).toContain("Source: https://openbooks.lumeo.co.in/docs/getting-started");
  });

  it("serves nested pages", async () => {
    const res = await mdGet(["cli", "run.md"]);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain("# Run command");
  });

  it("serves the root page for index.md", async () => {
    const res = await mdGet(["index.md"]);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain("# Open Books docs");
  });

  it.each([
    ["a path without the .md suffix", ["getting-started"]],
    ["a non-markdown suffix", ["getting-started.json"]],
    ["an unknown page", ["missing.md"]],
    ["a parent traversal", ["..", "secret.md"]],
    ["an encoded traversal left undecoded", ["%2e%2e", "secret.md"]],
    ["an uppercase variant of a real page", ["Getting-Started.md"]],
    ["an empty final segment", [""]],
  ])("answers 404 Not found for %s", async (_label, slug) => {
    const res = await mdGet(slug);
    expect(res.status).toBe(404);
    expect(await res.text()).toBe("Not found");
  });

  it("is configured to reject paths that were not generated at build time", () => {
    expect(llmsMarkdown.dynamicParams).toBe(false);
  });

  it("does not export POST", () => {
    expect(Object.keys(llmsMarkdown).filter((k) => /^[A-Z]+$/.test(k))).toEqual(["GET"]);
  });
});
