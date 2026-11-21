import { docs } from "@/lib/docs";
import { docsText, markdownSlugs, renderDocMarkdown } from "@/lib/docs-markdown";

export const dynamic = "force-static";
export const dynamicParams = false;
export const generateStaticParams = () => docs.getPages().map((page) => ({ slug: markdownSlugs(page) }));

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  const suffix = slug.at(-1);
  if (!suffix?.endsWith(".md")) return new Response("Not found", { status: 404 });
  const route = slug.length === 1 && suffix === "index.md"
    ? []
    : [...slug.slice(0, -1), suffix.slice(0, -3)];
  const page = docs.getPage(route);
  if (!page) return new Response("Not found", { status: 404 });
  return docsText(await renderDocMarkdown(page), "text/markdown", page.url);
}
