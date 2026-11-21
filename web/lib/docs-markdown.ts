import { docs } from "./docs";
import { siteUrl } from "./site";

type DocPage = ReturnType<typeof docs.getPages>[number];

export function markdownSlugs(page: DocPage): string[] {
  const slugs = page.slugs.length === 0 ? ["index"] : page.slugs;
  return [...slugs.slice(0, -1), slugs.at(-1) + ".md"];
}

export function markdownPath(page: DocPage): string {
  return "/llms/" + markdownSlugs(page).join("/");
}

export async function renderDocMarkdown(page: DocPage): Promise<string> {
  const raw = await page.data.getText("processed");
  const source = new URL(page.url, siteUrl).href;
  return [
    "# " + page.data.title,
    page.data.description,
    "Source: " + source,
    raw.trim(),
  ].filter(Boolean).join("\n\n") + "\n";
}

export function docsText(text: string, contentType = "text/plain", canonical?: string): Response {
  const headers = new Headers({
    "Content-Type": contentType + "; charset=utf-8",
  });
  if (canonical) headers.set("Link", "<" + new URL(canonical, siteUrl).href + '>; rel="canonical"');
  else headers.set("X-Robots-Tag", "googlebot: noindex");
  return new Response(text, { headers });
}
